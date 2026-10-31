# Contributing

Thanks for helping improve `roaring-presence`. The project is Linux-first and
keeps device/event handling in providers while one optional core owns Discord
IPC. Please keep the standalone audio-CD player useful without the Discord
core.

## Before opening a pull request

- Use Python 3.10 or newer and Bash.
- Keep tests offline and hardware-independent. Do not require a CD drive,
  running Discord client, game process, or desktop compositor in CI.
- Keep optional integrations optional. A missing Qt stack or `psutil` should
  produce a usable fallback or a clear diagnostic, not a traceback.
- Keep installation per-user by default. Do not add implicit `sudo`, alter
  Flatpak/Snap permissions, or overwrite existing user configuration.
- Do not put credentials, real user configuration, audio metadata caches, or
  machine-specific paths in the repository.

## Local validation

```bash
python3 -m py_compile \
  core/bin/roaring-presenced core/bin/roaring-presence-doctor \
  providers/audio-cd/bin/roaring-cd-presence \
  providers/audio-cd/bin/roaring-cd-session \
  providers/audio-cd/bin/roaring-cd-autoplay \
  providers/audio-cd/bin/cd_paths.py \
  providers/audio-cd/bin/roaring-cd-player \
  providers/minecraft/bin/roaring-minecraft-presence \
  tools/assets/bin/roaring-presence-art.py \
  tools/assets/bin/roaring-presence-assets tests/test_regressions.py
python3 -m unittest discover -s tests -v
bash -n install.sh providers/audio-cd/bin/roaring-presence-scan
```

CI runs the same offline tests on Python 3.10, 3.12, and 3.14 and verifies the
user systemd unit files. Include a regression test for every behavior fix.

## Component boundaries

- `providers/audio-cd/` owns CD detection, metadata, playback, MPRIS, and eject.
- Player-only sessions must not connect to the Discord manager.
- `core/` owns the single Discord IPC connection and provider arbitration.
- `providers/minecraft/` owns game-process discovery and lifecycle.
- `tools/assets/` stays an offline image-preparation tool.

See [architecture](docs/architecture.md) and
[Linux installation](docs/linux-installation.md) before changing packaging.
