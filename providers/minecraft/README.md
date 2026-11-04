# Minecraft provider

This provider reports a Java or Bedrock client session to the core publisher.
It is a separately installable source; it does not own a Discord connection.

## Activation and work model

The preferred activation is a launcher hook. Start
`roaring-minecraft-presence` from a Prism Launcher pre-launch command (or
start the supplied user unit):

```bash
systemctl --user start --no-block roaring-minecraft-presence.service
```

The unit waits up to 30 seconds for the client to appear. That short bounded
window is useful for a pre-launch hook, where Java may not exist at the exact
moment the hook fires. Set `minecraft.wait_seconds` to `0` for a direct
invocation that should only inspect an already-running client.

Once detected, the provider stops doing broad process-table discovery. On
modern Linux it attaches a pidfd and blocks until that exact process exits.
If an instance game directory is known, it also watches the instance's
`logs/` directory with inotify; changes to `latest.log` can update the
reported server/world without periodic rereads.

On kernels without pidfd support, it falls back to checking only the selected
PID's process-start identity at `minecraft.poll_seconds`, not scanning every
process. The short pre-launch discovery window is the only repeated discovery
step.

## Targeted mode

A launcher that can supply the game PID can avoid discovery entirely:

```bash
roaring-minecraft-presence --pid 12345
```

`--pid` is validated against known Minecraft launch signatures. It does not
blindly publish arbitrary process command lines.

## Activity details

The provider reports edition/version, mod loader, launcher instance, and
available multiplayer server or single-player world. It reads only the
instance's `logs/latest.log` tail when enabled and does not inspect process
open-file lists. With psutil absent it uses the Linux `/proc` interface.

## Test and debug

```bash
roaring-minecraft-presence --demo --once --dry-run
roaring-minecraft-presence --once --dry-run -v
journalctl --user -u roaring-minecraft-presence -f
```

Demo mode is synthetic and does not connect to Discord or require a game.
