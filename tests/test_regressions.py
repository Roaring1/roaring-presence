from __future__ import annotations

import importlib.util
import importlib.machinery
import json
import os
import select
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
# A normally launched Python script has its own directory on sys.path. Mirror
# that behavior for the source-file loader used by these hardware-free tests.
CD_BIN = ROOT / "providers/audio-cd/bin"
if str(CD_BIN) not in sys.path:
    sys.path.insert(0, str(CD_BIN))


def load_module(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    if spec is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


CORE = load_module("roaring_presence_core_test", ROOT / "core/bin/roaring-presenced")
DOCTOR = load_module("roaring_presence_doctor_test", ROOT / "core/bin/roaring-presence-doctor")
MINECRAFT = load_module(
    "roaring_presence_minecraft_test",
    ROOT / "providers/minecraft/bin/roaring-minecraft-presence",
)
CD = load_module("roaring_presence_cd_test", ROOT / "providers/audio-cd/bin/roaring-cd-presence")

PIL_AVAILABLE = importlib.util.find_spec("PIL") is not None
if PIL_AVAILABLE:
    ASSETS = load_module("roaring_presence_assets_test", ROOT / "tools/assets/bin/roaring-presence-assets")
    ART = load_module("roaring_presence_art_test", ROOT / "tools/assets/bin/roaring-presence-art.py")


class ManagerTests(unittest.TestCase):
    def test_activity_priority_arbitration(self):
        manager = CORE.Manager.__new__(CORE.Manager)
        manager.providers = {
            1: SimpleNamespace(name="minecraft", priority=10, activity={"details": "game"}, seq=1),
            2: SimpleNamespace(name="cd", priority=50, activity={"details": "disc"}, seq=2),
            3: SimpleNamespace(name="empty", priority=100, activity=None, seq=3),
        }
        self.assertEqual(manager.winner().name, "cd")

    def test_equal_priority_prefers_newest_provider(self):
        manager = CORE.Manager.__new__(CORE.Manager)
        manager.providers = {
            1: SimpleNamespace(name="old", priority=5, activity={"details": "old"}, seq=1),
            2: SimpleNamespace(name="new", priority=5, activity={"details": "new"}, seq=2),
        }
        self.assertEqual(manager.winner().name, "new")

    def test_provider_line_updates_metadata_and_activity(self):
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        peer = None
        left = None
        manager = None
        try:
            manager = CORE.Manager(
                {"client_id": "", "ipc_socket_candidates": [], "priorities": {"cd": 50}, "idle_exit_seconds": 1},
                server,
            )
            manager.publish = lambda: None
            left, peer = socket.socketpair()
            provider = CORE.Provider(left, 1)
            manager.providers[left.fileno()] = provider
            peer.sendall(b'{"provider":"cd","activity":{"details":"Listening"}}\n')
            manager.on_provider_readable(provider)
            self.assertEqual(provider.name, "cd")
            self.assertEqual(provider.priority, 50)
            self.assertEqual(provider.activity["details"], "Listening")
        finally:
            if peer is not None:
                peer.close()
            if left is not None:
                left.close()
            if manager is not None:
                manager.sel.close()
            server.close()

    def test_generic_discord_ipc_locations_are_defaulted(self):
        candidates = CORE.socket_candidate_templates([])
        self.assertEqual(candidates[0], "$XDG_RUNTIME_DIR/discord-ipc-{i}")
        for expected in (
            "$TMPDIR/discord-ipc-{i}",
            "$TMP/discord-ipc-{i}",
            "$TEMP/discord-ipc-{i}",
            "/tmp/discord-ipc-{i}",
            "$XDG_RUNTIME_DIR/app/com.discordapp.Discord/discord-ipc-{i}",
            "$XDG_RUNTIME_DIR/.flatpak/dev.vencord.Vesktop/xdg-run/discord-ipc-{i}",
            "$XDG_RUNTIME_DIR/snap.discord/discord-ipc-{i}",
        ):
            self.assertIn(expected, candidates)

    def test_custom_discord_ipc_paths_are_preferred_and_defaults_remain_fallbacks(self):
        custom = ["/custom/client/discord-ipc-{i}", "$XDG_RUNTIME_DIR/discord-ipc-{i}"]
        candidates = CORE.socket_candidate_templates(custom)
        self.assertEqual(candidates[:2], custom)
        self.assertIn("$TMPDIR/discord-ipc-{i}", candidates)
        self.assertEqual(len(candidates), len(set(candidates)))

    def test_discord_ipc_path_expands_standard_temp_variables(self):
        with mock.patch.dict(os.environ, {
            "XDG_RUNTIME_DIR": "/run/user/1234",
            "TMPDIR": "/var/tmp/user",
            "TMP": "/tmp/user",
            "TEMP": "/var/tmp/other",
        }):
            ipc = CORE.DiscordIPC("123456", ["$TMPDIR/custom-{i}"])
            paths = list(ipc._paths())
        self.assertEqual(paths[0], "/var/tmp/user/custom-0")
        self.assertIn("/run/user/1234/discord-ipc-0", paths)
        self.assertIn("/var/tmp/user/discord-ipc-0", paths)
        self.assertIn("/tmp/user/discord-ipc-0", paths)
        self.assertIn("/var/tmp/other/discord-ipc-0", paths)

    def test_discord_frame_encodes_little_endian_header(self):
        frame = CORE.DiscordIPC._frame(CORE.OP_FRAME, {"ok": True})
        op, length = struct.unpack("<II", frame[:8])
        self.assertEqual(op, CORE.OP_FRAME)
        self.assertEqual(length, len(frame) - 8)
        self.assertEqual(json.loads(frame[8:]), {"ok": True})


class MinecraftTests(unittest.TestCase):
    def test_targeted_process_reader_reads_only_requested_pid(self):
        record = MINECRAFT._read_proc_process(os.getpid())
        self.assertIsNotNone(record)
        self.assertEqual(record[0], os.getpid())
        self.assertIsInstance(record[1], float)
        self.assertTrue(record[2])

    def test_targeted_discovery_passes_pid_to_process_iterator(self):
        record = (
            4321,
            time.time() - 10,
            "java org.prismlauncher.EntryPoint --version 1.21.1 --gameDir /tmp/instances/Test/.minecraft",
        )
        with mock.patch.object(MINECRAFT, "_iter_processes", return_value=iter([record])) as iterator:
            found = MINECRAFT.find_minecraft(4321)
        iterator.assert_called_once_with(4321)
        self.assertEqual(found["pid"], 4321)
        self.assertEqual(found["version"], "1.21.1")
        self.assertEqual(found["instance"], "Test")

    def test_activity_uses_configured_generic_asset_key(self):
        meta = {
            "edition": "java",
            "version": "1.21.1",
            "loader": "Fabric",
            "instance": "Example Pack",
            "start": time.time() - 30,
        }
        activity = MINECRAFT.build_activity(meta, {
            "assets": {"minecraft": "my-pack-game"},
            "minecraft": {"show_instance": True},
        })
        self.assertEqual(activity["assets"]["large_image"], "my-pack-game")
        self.assertIn("Fabric", activity["details"])
        self.assertEqual(activity["state"], "Example Pack")

    def test_activity_uses_generic_default_asset_key(self):
        meta = {
            "edition": "java",
            "version": "1.21.1",
            "start": time.time() - 30,
        }
        activity = MINECRAFT.build_activity(meta, {"assets": {}, "minecraft": {}})
        self.assertEqual(activity["assets"]["large_image"], "minecraft")

    def test_inotify_watches_late_logs_directory_and_latest_log_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            watcher = MINECRAFT.InotifyLogWatch(tmp)
            try:
                logs = Path(tmp) / "logs"
                logs.mkdir()
                ready, _, _ = select.select([watcher.fd], [], [], 2)
                self.assertTrue(ready, "expected the new logs directory event")
                self.assertTrue(watcher.changed())
                self.assertGreaterEqual(watcher.logs_watch, 0)

                log_path = logs / "latest.log"
                log_path.write_text("Connecting to example.test\n", encoding="utf-8")
                ready, _, _ = select.select([watcher.fd], [], [], 2)
                self.assertTrue(ready, "expected latest.log create/write event")
                self.assertTrue(watcher.changed())
            finally:
                watcher.close()

    def test_inotify_ignores_unrelated_file_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            logs.mkdir()
            watcher = MINECRAFT.InotifyLogWatch(tmp)
            try:
                (logs / "unrelated.txt").write_text("hello", encoding="utf-8")
                ready, _, _ = select.select([watcher.fd], [], [], 2)
                self.assertTrue(ready)
                self.assertFalse(watcher.changed())
            finally:
                watcher.close()


    def test_watch_session_exits_on_pidfd_process_exit(self):
        if not hasattr(os, "pidfd_open"):
            self.skipTest("pidfd_open is unavailable on this kernel")
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        killer = None
        try:
            record = None
            deadline = time.monotonic() + 2.0
            while record is None and time.monotonic() < deadline:
                record = MINECRAFT._read_proc_process(child.pid)
                if record is None:
                    time.sleep(0.02)
            self.assertIsNotNone(record)
            killer = threading.Thread(
                target=lambda: (time.sleep(0.15), child.terminate()),
                daemon=True,
            )
            killer.start()
            started = time.monotonic()
            MINECRAFT.watch_session(
                {"pid": child.pid, "start": record[1]},
                {"read_logs": False},
                10.0,
                [],
                lambda: None,
            )
            elapsed = time.monotonic() - started
            self.assertLess(elapsed, 2.0, "pidfd watcher should wake on process exit")
            child.wait(timeout=2)
            killer.join(timeout=2)
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=2)
            if killer is not None:
                killer.join(timeout=2)


class AudioCdPlayerIntegrationTests(unittest.TestCase):
    def test_session_stops_leftover_owned_process_group_after_player_crash(self):
        process = mock.Mock()
        process.pid = 4321
        process.poll.return_value = 23
        with mock.patch.object(CD.os, "killpg") as killpg, \
             mock.patch.object(CD.time, "sleep") as sleep:
            CD.stop_player(process)
        self.assertEqual(
            killpg.call_args_list,
            [
                mock.call(4321, 0),
                mock.call(4321, CD.signal.SIGTERM),
                mock.call(4321, CD.signal.SIGKILL),
            ],
        )
        sleep.assert_called_once_with(0.25)
        process.wait.assert_not_called()

    def test_player_only_session_does_not_construct_discord_manager_link(self):
        with mock.patch.object(CD, "ManagerLink") as manager_link:
            self.assertIsNone(CD.manager_link_for_mode(player_only=True))
        manager_link.assert_not_called()

    def test_discord_session_still_connects_through_shared_manager(self):
        with mock.patch.object(CD, "ManagerLink") as manager_link:
            manager_link.return_value.connect.return_value = True
            result = CD.manager_link_for_mode(player_only=False)
        self.assertIs(result, manager_link.return_value)
        manager_link.return_value.connect.assert_called_once_with()

    def test_cd_ipc_socket_is_private_per_drive_and_preserves_custom_paths(self):
        socket0 = CD.mpv_socket_path("/dev/sr0")
        socket1 = CD.mpv_socket_path("/dev/sr1")
        self.assertNotEqual(socket0, socket1)
        self.assertTrue(socket0.endswith("roaring-cd-mpv-sr0.sock"))
        self.assertTrue(socket1.endswith("roaring-cd-mpv-sr1.sock"))
        self.assertEqual(
            CD.mpv_socket_path("/dev/sr1", "$XDG_RUNTIME_DIR/mpv-ipc.sock"),
            socket1,
        )
        self.assertEqual(
            CD.mpv_socket_path("/dev/sr1", "/tmp/my-custom-cd.sock"),
            "/tmp/my-custom-cd.sock",
        )
        player_source = (CD_BIN / "roaring-cd-player").read_text(encoding="utf-8")
        self.assertIn("def mpv_socket_path(", player_source)

    def test_session_launches_its_sibling_player_without_a_systemd_scope(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(CD.subprocess, "Popen", return_value=SimpleNamespace(pid=123)) as popen, \
             mock.patch.dict(os.environ, {"XDG_CACHE_HOME": tmp}):
            process = CD.launch_player({"device": "/dev/sr0", "tracks": []})

        binary = str((CD_BIN / "roaring-cd-player").resolve())
        self.assertEqual(process.pid, 123)
        argv = popen.call_args.args[0]
        self.assertEqual(argv[:3], [binary, "--device", "/dev/sr0"])
        self.assertIn("--json", argv)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertNotIn("systemd-run", argv)
        self.assertNotIn("roaring-cd-autoplay", " ".join(argv))

    def test_standalone_session_waits_for_player_without_observing_mpv(self):
        process = mock.Mock()
        process.wait.return_value = 0
        process.poll.return_value = 0
        process.pid = 123
        with mock.patch.object(CD.os, "killpg", side_effect=ProcessLookupError) as killpg:
            CD.wait_for_player(process)
        process.wait.assert_called_once_with()
        killpg.assert_called_once_with(123, 0)

    def test_standalone_session_propagates_unexpected_player_exit(self):
        process = mock.Mock()
        process.wait.return_value = 7
        process.poll.return_value = 7
        process.returncode = 7
        process.pid = 123
        with mock.patch.object(CD.os, "killpg", side_effect=ProcessLookupError):
            result = CD.wait_for_player(process)
        self.assertEqual(result, 7)

    def test_session_stops_and_reaps_only_its_player_child(self):
        process = mock.Mock()
        process.poll.return_value = None
        CD.stop_player(process)
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=5.5)

    def test_player_only_entry_point_exposes_help_without_launching_a_disc(self):
        result = subprocess.run(
            [str(CD_BIN / "roaring-cd-presence"), "--player-only", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--player-only", result.stdout)

    def test_catchup_scanner_rejects_unknown_options(self):
        result = subprocess.run(
            ["bash", str(ROOT / "providers/audio-cd/bin/roaring-presence-scan"), "--unknown"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown option", result.stderr)


class AudioCdMetadataTests(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.TemporaryDirectory()
        self.previous_cache = CD.CACHE_DIR
        CD.CACHE_DIR = self.cache.name
        self.disc = {
            "toc": {1: 150, 2: 15000},
            "leadout": 30000,
            "album": "Example Album",
            "artist": "Example Artist",
        }

    def tearDown(self):
        CD.CACHE_DIR = self.previous_cache
        self.cache.cleanup()

    def test_disc_id_lookup_uses_release_group_when_release_has_no_art(self):
        release = {
            "id": "release-id",
            "title": "Example Album",
            "artist-credit": [{"name": "Example Artist"}],
            "media": [{"tracks": [{"position": "1", "title": "Opening"}]}],
            "release-group": {"id": "group-id"},
        }
        cover = "https://coverartarchive.org/release/example/front-500.jpg"
        with mock.patch.object(CD, "http_json", return_value={"releases": [release]}) as request, \
             mock.patch.object(CD, "caa_front", side_effect=[None, cover]) as art:
            result = CD.resolve_metadata(self.disc, True, True)

        self.assertEqual(result["release_group_id"], "group-id")
        self.assertEqual(result["cover"], cover)
        self.assertTrue(result["cover_art_checked"])
        self.assertIn("release-groups", request.call_args.args[0])
        self.assertEqual(
            art.call_args_list,
            [mock.call("release", "release-id"), mock.call("release-group", "group-id")],
        )

    def test_old_cache_backfills_release_group_cover_once(self):
        discid = CD.musicbrainz_discid(self.disc["toc"], self.disc["leadout"])
        cache_file = Path(self.cache.name) / f"disc-{discid}.v2.json"
        cache_file.write_text(json.dumps({
            "discid": discid,
            "release_id": "release-id",
            "cover": None,
            "mb_titles": {"1": "Opening"},
            "mb_album": "Example Album",
            "mb_artist": "Example Artist",
        }), encoding="utf-8")
        cover = "https://coverartarchive.org/release/example/front-500.jpg"

        with mock.patch.object(
            CD, "mb_release_details", return_value={"release-group": {"id": "group-id"}}
        ) as details, mock.patch.object(CD, "caa_front", side_effect=[None, cover]) as art:
            result = CD.resolve_metadata(self.disc, True, True)

        self.assertEqual(result["release_group_id"], "group-id")
        self.assertEqual(result["cover"], cover)
        details.assert_called_once_with("release-id")
        self.assertEqual(
            art.call_args_list,
            [mock.call("release", "release-id"), mock.call("release-group", "group-id")],
        )
        saved = json.loads(cache_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["cover"], cover)
        self.assertTrue(saved["cover_art_checked"])

    def test_activity_is_absent_when_idle_or_paused(self):
        metadata = {"mb_album": "Example Album", "mb_artist": "Example Artist"}
        config = {"assets": {"cd": "cd", "play": "play", "pause": "pause"}}
        for state in (
            {"playing": False, "paused": False},
            {"playing": True, "paused": True},
            {"playing": None, "paused": False},
        ):
            with self.subTest(state=state):
                self.assertIsNone(CD.build_activity(self.disc, metadata, config, state))

    def test_activity_exists_only_for_confirmed_unpaused_playback(self):
        activity = CD.build_activity(
            self.disc,
            {"mb_album": "Example Album", "mb_artist": "Example Artist", "mb_titles": {1: "Opening"}},
            {"assets": {"cd": "cd", "play": "play"}},
            {"track": 1, "playing": True, "paused": False, "elapsed": 15, "length": 198},
        )
        self.assertIsNotNone(activity)
        self.assertEqual(activity["details"], "Opening")

    def test_observer_fails_closed_for_missing_or_paused_mpv_state(self):
        for mpv_state in (
            {},
            {"path": "cdda://", "pause": True, "time-pos": 0},
            {"path": "cdda://", "pause": None, "time-pos": 10},
        ):
            with self.subTest(mpv_state=mpv_state), mock.patch.object(CD, "mpv_query", return_value=mpv_state):
                state = CD.observe_playback(self.disc, {"cd": {"mpv_ipc_socket": "/tmp/fake.sock"}})
            self.assertFalse(state["playing"])
            self.assertIsNone(CD.build_activity(self.disc, {}, {}, state))

    def test_observer_maps_confirmed_mpv_position_to_track(self):
        mpv_state = {"path": "cdda://", "pause": False, "time-pos": 20.0}
        with mock.patch.object(CD, "mpv_query", return_value=mpv_state):
            state = CD.observe_playback(self.disc, {"cd": {"mpv_ipc_socket": "/tmp/fake.sock"}})
        self.assertTrue(state["playing"])
        self.assertFalse(state["paused"])
        self.assertEqual(state["track"], 1)
        self.assertAlmostEqual(state["elapsed"], 18.0)

    def test_resolved_cover_url_wins_over_generic_cd_asset(self):
        cover = "https://coverartarchive.org/release/example/front-500.jpg"
        activity = CD.build_activity(
            self.disc,
            {
                "discid": "example-disc",
                "cover": cover,
                "mb_album": "Example Album",
                "mb_artist": "Example Artist",
                "mb_titles": {1: "Opening"},
            },
            {"assets": {"cd": "generic-cd", "play": "play"}},
            {"track": 1, "playing": True, "paused": False, "elapsed": 15, "length": 240},
        )
        self.assertEqual(activity["assets"]["large_image"], cover)

    def test_disabling_musicbrainz_is_offline_and_keeps_disc_id(self):
        with mock.patch.object(CD, "http_json", side_effect=AssertionError("network called")), \
             mock.patch.object(CD, "mb_search_release", side_effect=AssertionError("search called")):
            result = CD.resolve_metadata(self.disc, False, False)
        self.assertTrue(result["discid"])
        self.assertEqual(result["mb_titles"], {})

    def test_cover_art_off_does_not_disable_musicbrainz_track_titles(self):
        release = {
            "id": "release-id",
            "title": "Example Album",
            "artist-credit": [{"name": "Example Artist"}],
            "media": [{"tracks": [{"position": "1", "title": "Opening"}]}],
            "release-group": {"id": "group-id"},
        }
        with mock.patch.object(CD, "http_json", return_value={"releases": [release]}), \
             mock.patch.object(CD, "caa_front", side_effect=AssertionError("art endpoint called")):
            result = CD.resolve_metadata(self.disc, True, False)
        self.assertEqual(result["mb_titles"], {1: "Opening"})
        self.assertEqual(result["mb_artist"], "Example Artist")
        self.assertIsNone(result["cover"])

    def test_disabling_cover_art_suppresses_cached_cover_but_keeps_titles(self):
        release = {
            "id": "release-id",
            "title": "Example Album",
            "artist-credit": [{"name": "Example Artist"}],
            "media": [{"tracks": [{"position": "1", "title": "Opening"}]}],
            "release-group": {"id": "group-id"},
        }
        with mock.patch.object(CD, "http_json", return_value={"releases": [release]}), \
             mock.patch.object(CD, "caa_front", return_value="https://example.test/cover.jpg"):
            enabled = CD.resolve_metadata(self.disc, True, True)
        self.assertEqual(enabled["cover"], "https://example.test/cover.jpg")
        with mock.patch.object(CD, "http_json", side_effect=AssertionError("cache miss")), \
             mock.patch.object(CD, "caa_front", side_effect=AssertionError("art endpoint called")):
            disabled = CD.resolve_metadata(self.disc, True, False)
        self.assertIsNone(disabled["cover"])
        self.assertEqual(disabled["mb_titles"], {1: "Opening"})


class DoctorTests(unittest.TestCase):
    def test_cd_player_doctor_does_not_require_discord_configuration_or_socket(self):
        old_config = DOCTOR.CONFIG_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                DOCTOR.CONFIG_PATH = Path(tmp) / "no-config.json"
                with mock.patch.object(DOCTOR, "manager_status", side_effect=AssertionError("Discord manager must not be checked")), \
                     mock.patch.object(DOCTOR, "check_command"), \
                     mock.patch.object(DOCTOR, "python_module_available", return_value=True), \
                     mock.patch.object(DOCTOR, "mpv_audio_outputs", return_value={"pipewire", "pulse"}):
                    results, summary = DOCTOR.run(component="cd-player")
            self.assertEqual(summary["errors"], 0)
            self.assertFalse(any(item["area"] in ("discord-ipc", "manager") for item in results))
            self.assertFalse(any("Application ID" in item["message"] for item in results))
        finally:
            DOCTOR.CONFIG_PATH = old_config

    def test_cd_player_doctor_does_not_require_psutil(self):
        old_config = DOCTOR.CONFIG_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                DOCTOR.CONFIG_PATH = Path(tmp) / "no-config.json"

                def module_available(name):
                    return name != "psutil"

                with mock.patch.object(DOCTOR, "check_command"), \
                     mock.patch.object(DOCTOR, "python_module_available", side_effect=module_available), \
                     mock.patch.object(DOCTOR, "mpv_protocols", return_value={"cdda"}), \
                     mock.patch.object(DOCTOR, "mpv_audio_outputs", return_value={"pulse"}):
                    results, summary = DOCTOR.run(component="cd-player")
            self.assertEqual(summary["errors"], 0)
            self.assertFalse(any("psutil" in item["message"] for item in results))
        finally:
            DOCTOR.CONFIG_PATH = old_config

    def test_cd_player_doctor_checks_for_the_eject_command(self):
        old_config = DOCTOR.CONFIG_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                DOCTOR.CONFIG_PATH = Path(tmp) / "no-config.json"
                with mock.patch.object(DOCTOR, "check_command") as check_command, \
                     mock.patch.object(DOCTOR, "python_module_available", return_value=True), \
                     mock.patch.object(DOCTOR, "mpv_protocols", return_value={"cdda"}), \
                     mock.patch.object(DOCTOR, "mpv_audio_outputs", return_value={"pulse"}):
                    DOCTOR.run(component="cd-player")
            names = [call.args[1] for call in check_command.call_args_list]
            self.assertIn("eject", names)
        finally:
            DOCTOR.CONFIG_PATH = old_config

    def test_cd_player_doctor_requires_qtdbus_for_mpris_controls(self):
        old_config = DOCTOR.CONFIG_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                DOCTOR.CONFIG_PATH = Path(tmp) / "no-config.json"

                def module_available(name):
                    return name != "PyQt6.QtDBus"

                with mock.patch.object(DOCTOR, "check_command"), \
                     mock.patch.object(DOCTOR, "python_module_available", side_effect=module_available), \
                     mock.patch.object(DOCTOR, "mpv_protocols", return_value={"cdda"}), \
                     mock.patch.object(DOCTOR, "mpv_audio_outputs", return_value={"pulse"}):
                    results, summary = DOCTOR.run(component="cd-player")
            self.assertEqual(summary["errors"], 1)
            self.assertTrue(any("QtDBus" in item["message"] and item["level"] == "error" for item in results))
        finally:
            DOCTOR.CONFIG_PATH = old_config

    def test_mpv_audio_driver_parser_detects_whitespace_separated_names(self):
        with mock.patch.object(DOCTOR.shutil, "which", return_value="/usr/bin/mpv"), \
             mock.patch.object(
                 DOCTOR.subprocess, "run",
                 return_value=SimpleNamespace(
                     stdout="Available audio outputs:\n  pipewire         PipeWire output\n  pulse            PulseAudio output\n",
                     stderr="",
                 ),
             ):
            self.assertEqual(DOCTOR.mpv_audio_outputs(), {"pipewire", "pulse"})

    def test_mpv_protocol_parser_detects_cdda_support(self):
        with mock.patch.object(DOCTOR.shutil, "which", return_value="/usr/bin/mpv"), \
             mock.patch.object(
                 DOCTOR.subprocess, "run",
                 return_value=SimpleNamespace(
                     stdout="Protocols:\n\n cdda://\n file://\n http://\n",
                     stderr="",
                 ),
             ):
            self.assertEqual(DOCTOR.mpv_protocols(), {"cdda", "file", "http"})

    def test_doctor_checks_generic_paths_even_with_old_client_specific_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "runtime"
            runtime.mkdir()
            native_socket = runtime / "discord-ipc-0"
            stale_path = runtime / "discord-ipc-1"
            stale_path.write_text("not a socket", encoding="utf-8")
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                listener.bind(str(native_socket))
                with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(runtime)}):
                    found = DOCTOR.candidate_socket_paths([
                        "$XDG_RUNTIME_DIR/.flatpak/dev.vencord.Vesktop/xdg-run/discord-ipc-{i}"
                    ])
                self.assertEqual(found, [native_socket])
            finally:
                listener.close()

    def test_default_doctor_does_not_connect_to_manager_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_root = Path(tmp) / "config"
            config_dir = config_root / "roaring-presence"
            config_dir.mkdir(parents=True)
            (config_dir / "config.json").write_text(json.dumps({
                "client_id": "123456789012345678",
                "ipc_socket_candidates": [],
                "assets": {"minecraft": "minecraft"},
            }), encoding="utf-8")
            old_config = DOCTOR.CONFIG_PATH
            old_runtime = DOCTOR.runtime_dir
            DOCTOR.CONFIG_PATH = config_dir / "config.json"
            DOCTOR.runtime_dir = lambda: Path(tmp) / "runtime"
            try:
                with mock.patch.object(DOCTOR.socket, "socket", side_effect=AssertionError("socket connected")), \
                     mock.patch.object(DOCTOR, "check_command"), \
                     mock.patch.object(DOCTOR, "python_module_available", return_value=True), \
                     mock.patch.object(DOCTOR, "mpv_protocols", return_value={"cdda"}), \
                     mock.patch.object(DOCTOR, "mpv_audio_outputs", return_value={"pulse"}):
                    results, summary = DOCTOR.run()
                self.assertEqual(summary["errors"], 0)
                self.assertTrue(any("socket path" in item["message"] or "socket unit" in item["message"] for item in results))
            finally:
                DOCTOR.CONFIG_PATH = old_config
                DOCTOR.runtime_dir = old_runtime


@unittest.skipUnless(PIL_AVAILABLE, "Pillow is not installed")
class AssetToolTests(unittest.TestCase):
    def test_generic_asset_pack_handles_named_and_filename_keys(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "Wide Logo.PNG"
            Image.new("RGBA", (320, 160), (255, 30, 20, 255)).save(source)
            output = root / "packed"
            code = ASSETS.main([
                "--output-dir", str(output), "--size", "128", "--fit", "contain",
                "Studio Logo=" + str(source),
            ])
            self.assertEqual(code, 0)
            with Image.open(output / "studio-logo.png") as result:
                self.assertEqual(result.size, (128, 128))
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["assets"][0]["key"], "studio-logo")
            self.assertNotIn(str(root), json.dumps(manifest))

    def test_generic_asset_pack_rejects_duplicate_normalized_keys(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            one = root / "one.png"
            two = root / "two.png"
            Image.new("RGB", (16, 16), "red").save(one)
            Image.new("RGB", (16, 16), "blue").save(two)
            code = ASSETS.main([str(one), "ONE=" + str(two), "--output-dir", str(root / "out")])
            self.assertEqual(code, 2)

    def test_generic_asset_pack_refuses_overwrite_without_flag(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            Image.new("RGB", (16, 16), "red").save(source)
            output = root / "out"
            self.assertEqual(ASSETS.main(["--output-dir", str(output), str(source)]), 0)
            original = (output / "source.png").read_bytes()
            self.assertEqual(ASSETS.main(["--output-dir", str(output), str(source)]), 2)
            self.assertEqual((output / "source.png").read_bytes(), original)

    def test_builtin_art_generator_honors_custom_directory_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "custom"
            code = ART.main(["--output-dir", str(output), "--size", "128", "--key-prefix", "my-app"])
            self.assertEqual(code, 0)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            assets = {item["key"]: item["file"] for item in manifest["assets"]}
            self.assertEqual(assets["my-app-minecraft"], "asset_minecraft.png")
            for filename in assets.values():
                self.assertTrue((output / filename).is_file())
            self.assertTrue((output / "icon.png").is_file())


if __name__ == "__main__":
    unittest.main()


class ProjectMetadataTests(unittest.TestCase):
    def test_mit_license_citation_and_dependency_boundary_are_consistent(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Copyright (c) 2026 Roaring", license_text)
        self.assertIn("Permission is hereby granted", license_text)
        self.assertIn("license: MIT", citation)
        self.assertIn("does not relicense them", notices)
        self.assertIn("[MIT License](LICENSE)", readme)


class InstallerSmokeTests(unittest.TestCase):
    def run_installer(self, *args, seed_legacy=False, seed_config=False):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        home = root / "home"
        home.mkdir()
        if seed_config:
            config_dir = root / "xdg-config/roaring-presence"
            config_dir.mkdir(parents=True)
            (config_dir / "config.json").write_text(
                json.dumps({
                    "client_id": "preserve-this-id",
                    "assets": {"cd": "custom-cd", "minecraft": "custom-world"},
                    "cd": {
                        "mpv_ipc_socket": "$XDG_RUNTIME_DIR/mpv-ipc.sock",
                        "autoplay_prompt": True,
                        "preload": True,
                        "preload_idle_seconds": 60,
                        "idle_poll_seconds": 6,
                        "player_ui": True,
                        "player_poll_seconds": 1,
                        "player_idle_poll_seconds": 3,
                        "progress_drift_seconds": 4.0,
                        "links": {"track": "https://example.test/%(query)s"},
                    },
                    "minecraft": {"poll_seconds": 17, "show_world": False},
                }, indent=2) + "\n",
                encoding="utf-8",
            )
            (config_dir / "config.json").chmod(0o600)
        if seed_legacy:
            local_bin = home / ".local/bin"
            local_bin.mkdir(parents=True)
            managed = {
                "roaring-cd-autoplay": '#!/usr/bin/env python3\n"""roaring-cd-autoplay -- extremely minimal"""\n',
                "roaring-cd-session": '#!/usr/bin/env python3\n"""Standalone audio-CD session entry point"""\n',
                "cd_paths.py": '"""Small shared path helpers for the standalone audio-CD tools."""\n',
            }
            for name, content in managed.items():
                (local_bin / name).write_text(content, encoding="utf-8")
            (local_bin / "user-owned-tool").write_text("do not remove\n", encoding="utf-8")
            legacy_bin = home / "bin"
            legacy_bin.mkdir()
            for name in managed:
                (legacy_bin / name).symlink_to(local_bin / name)
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        systemctl = fake_bin / "systemctl"
        systemctl.write_text(
            "#!/bin/sh\ncase \" $* \" in *\" is-enabled \"*) exit 1 ;; esac\nexit 0\n",
            encoding="utf-8",
        )
        systemctl.chmod(0o755)
        env = os.environ.copy()
        env.update({
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(root / "xdg-config"),
            "PATH": str(fake_bin) + ":/usr/local/bin:/usr/bin:/bin",
            "XDG_RUNTIME_DIR": str(root / "runtime"),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent/test-bus",
        })
        result = subprocess.run(
            ["bash", str(ROOT / "install.sh"), *args],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            temporary.cleanup()
            self.fail(f"installer failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
        return temporary, home, root, result

    def test_default_install_is_player_only_and_desktop_exec_is_absolute(self):
        temporary, home, root, result = self.run_installer()
        self.addCleanup(temporary.cleanup)
        bin_dir = home / ".local/bin"
        config_root = root / "xdg-config"
        self.assertTrue((bin_dir / "roaring-cd-presence").is_file())
        self.assertTrue((bin_dir / "roaring-cd-player").is_file())
        self.assertFalse((bin_dir / "roaring-cd-session").exists())
        self.assertFalse((bin_dir / "roaring-cd-autoplay").exists())
        self.assertFalse((bin_dir / "cd_paths.py").exists())
        self.assertTrue((bin_dir / "roaring-presence-doctor").is_file())
        self.assertFalse((bin_dir / "roaring-presenced").exists())
        self.assertFalse((config_root / "roaring-presence/config.json").exists())
        self.assertTrue((config_root / "systemd/user/roaring-cd-player@.service").is_file())
        self.assertIn("roaring-presence-doctor --component cd-player", result.stdout)
        self.assertIn("roaring-cd-presence --player-only /dev/sr0", result.stdout)
        self.assertFalse((config_root / "systemd/user/roaring-presenced.socket").exists())
        desktop = (home / ".local/share/applications/roaring-cd-player.desktop").read_text(encoding="utf-8")
        self.assertIn(f"Exec={bin_dir}/roaring-presence-scan --player-only", desktop)
        self.assertNotIn("@ROARING_PRESENCE_EXEC@", desktop)
        updater = bin_dir / "roaring-presence-update"
        self.assertTrue(updater.is_file())
        subprocess.run(["bash", "-n", str(updater)], check=True, timeout=10)
        help_result = subprocess.run([str(updater), "--help"], capture_output=True, text=True, timeout=10)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        updater_source = updater.read_text(encoding="utf-8")
        self.assertIn("--check", updater_source)
        self.assertIn("VERIFY_DIR", updater_source)
        self.assertIn("PROFILE_ARGS=(--component cd-player", updater_source)
        self.assertIn("UPDATE_CD_MODE=player", updater_source)
        self.assertNotIn("providers/audio-cd/bin/roaring-cd-session", updater_source)
        self.assertNotIn("providers/audio-cd/bin/cd_paths.py", updater_source)
        self.assertIn("UPDATE_MINECRAFT", updater_source)
        self.assertIn("UPDATER_TMP", (ROOT / "install.sh").read_text(encoding="utf-8"))
        self.assertIn("mv -f \"$UPDATER_TMP\"", (ROOT / "install.sh").read_text(encoding="utf-8"))

    def test_upgrade_migrates_only_obsolete_cd_settings(self):
        temporary, home, root, _result = self.run_installer(seed_config=True)
        self.addCleanup(temporary.cleanup)
        config = json.loads(
            (root / "xdg-config/roaring-presence/config.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["client_id"], "preserve-this-id")
        self.assertEqual(config["assets"], {"cd": "custom-cd", "minecraft": "custom-world"})
        self.assertEqual(config["minecraft"], {"poll_seconds": 17, "show_world": False})
        self.assertEqual(
            config["cd"]["mpv_ipc_socket"],
            "$XDG_RUNTIME_DIR/roaring-cd-mpv.sock",
        )
        self.assertEqual(config["cd"]["progress_drift_seconds"], 4.0)
        self.assertEqual(
            config["cd"]["links"],
            {"track": "https://example.test/%(query)s"},
        )
        for obsolete in (
            "autoplay_prompt", "preload", "preload_idle_seconds",
            "idle_poll_seconds", "player_ui", "player_poll_seconds",
            "player_idle_poll_seconds",
        ):
            self.assertNotIn(obsolete, config["cd"])
        config_path = root / "xdg-config/roaring-presence/config.json"
        self.assertEqual(config_path.stat().st_mode & 0o777, 0o600)

    def test_upgrade_preserves_custom_mpv_socket(self):
        temporary, home, root, _result = self.run_installer(seed_config=True)
        self.addCleanup(temporary.cleanup)
        config_path = root / "xdg-config/roaring-presence/config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["cd"]["mpv_ipc_socket"] = "/run/user/1000/custom-audio.sock"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        # Re-running installation is idempotent and must not replace a custom socket.
        env = os.environ.copy()
        env.update({
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "PATH": "/usr/bin:/bin",
            "XDG_RUNTIME_DIR": str(home / "runtime"),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent/test-bus",
        })
        subprocess.run(
            ["bash", str(ROOT / "install.sh")], cwd=ROOT, env=env,
            capture_output=True, text=True, timeout=30, check=True,
        )
        migrated = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(migrated["cd"]["mpv_ipc_socket"], "/run/user/1000/custom-audio.sock")

    def test_upgrade_removes_only_managed_legacy_cd_helpers(self):
        temporary, home, _root, _result = self.run_installer(seed_legacy=True)
        self.addCleanup(temporary.cleanup)
        local_bin = home / ".local/bin"
        legacy_bin = home / "bin"
        for name in ("roaring-cd-autoplay", "roaring-cd-session", "cd_paths.py"):
            self.assertFalse((local_bin / name).exists())
            self.assertFalse((legacy_bin / name).exists())
        self.assertEqual((local_bin / "user-owned-tool").read_text(encoding="utf-8"), "do not remove\n")

    def test_all_profile_generates_presence_aware_update_recipe(self):
        temporary, home, root, _result = self.run_installer("--component", "all")
        self.addCleanup(temporary.cleanup)
        config_root = root / "xdg-config"
        bin_dir = home / ".local/bin"
        self.assertTrue((config_root / "systemd/user/roaring-presenced.socket").is_file())
        self.assertTrue((config_root / "systemd/user/roaring-cd-presence@.service").is_file())
        self.assertIn("roaring-presence-doctor --component audio-cd", _result.stdout)
        desktop = (home / ".local/share/applications/roaring-cd-player.desktop").read_text(encoding="utf-8")
        self.assertIn(f"Exec={bin_dir}/roaring-presence-scan\n", desktop)
        self.assertNotIn("--player-only", desktop)
        self.assertFalse((config_root / "systemd/user/roaring-cd-player@.service").exists())
        self.assertTrue((bin_dir / "roaring-minecraft-presence").is_file())
        self.assertTrue((bin_dir / "roaring-presence-assets").is_file())
        updater = (bin_dir / "roaring-presence-update").read_text(encoding="utf-8")
        self.assertIn("UPDATE_CORE=1", updater)
        self.assertIn("UPDATE_CD_MODE=presence", updater)
        self.assertIn("UPDATE_MINECRAFT=1", updater)

    def test_nondefault_xdg_data_home_receives_desktop_entry(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        home = root / "home"
        home.mkdir()
        data_home = root / "data-home"
        config_home = root / "config-home"
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        systemctl = fake_bin / "systemctl"
        systemctl.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        systemctl.chmod(0o755)
        env = os.environ.copy()
        env.update({
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(config_home),
            "XDG_DATA_HOME": str(data_home),
            "PATH": str(fake_bin) + ":/usr/local/bin:/usr/bin:/bin",
            "XDG_RUNTIME_DIR": str(root / "runtime"),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent/test-bus",
        })
        result = subprocess.run(
            ["bash", str(ROOT / "install.sh"), "--component", "cd-player"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((data_home / "applications/roaring-cd-player.desktop").is_file())
        self.assertFalse((home / ".local/share/applications/roaring-cd-player.desktop").exists())
        self.assertTrue((config_home / "systemd/user/roaring-cd-player@.service").is_file())

    def test_discord_cd_profile_installs_core_and_preserves_existing_config(self):
        temporary, home, root, _result = self.run_installer("--component", "discord-cd")
        self.addCleanup(temporary.cleanup)
        bin_dir = home / ".local/bin"
        config_root = root / "xdg-config"
        self.assertTrue((bin_dir / "roaring-presenced").is_file())
        self.assertTrue((config_root / "systemd/user/roaring-presenced.socket").is_file())
        self.assertTrue((config_root / "systemd/user/roaring-cd-presence@.service").is_file())
        self.assertFalse((config_root / "systemd/user/roaring-cd-player@.service").exists())
        config = config_root / "roaring-presence/config.json"
        self.assertTrue(config.is_file())
        config.write_text('{"client_id":"kept"}\n', encoding="utf-8")
        # A reinstall must not replace the user's file.
        reinstall_env = os.environ.copy()
        fake_bin = root / "fake-bin"
        reinstall_env.update({
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(config_root),
            "PATH": str(fake_bin) + ":/usr/local/bin:/usr/bin:/bin",
            "XDG_RUNTIME_DIR": str(root / "runtime"),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent/test-bus",
        })
        result = subprocess.run(
            ["bash", str(ROOT / "install.sh"), "--component", "audio-cd"],
            cwd=ROOT, env=reinstall_env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(config.read_text(encoding="utf-8"), '{"client_id":"kept"}\n')
