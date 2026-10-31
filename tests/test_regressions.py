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
CD_AUTOPLAY = load_module(
    "roaring_presence_cd_autoplay_test",
    ROOT / "providers/audio-cd/bin/roaring-cd-autoplay",
)

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
    def test_mpv_stream_has_kde_task_identity(self):
        argv = CD_AUTOPLAY.mpv_argv("/dev/sr0", 2)
        self.assertIn("--ao=pulse", argv)
        self.assertIn("--audio-client-name=Audio CD", argv)
        self.assertIn("--cdda-device=/dev/sr0", argv)


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
                with mock.patch.object(DOCTOR.socket, "socket", side_effect=AssertionError("socket connected")):
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
