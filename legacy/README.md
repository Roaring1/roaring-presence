# Legacy compatibility files

This directory retains two older approaches for reference during migration:

- `roaring_vesktop_minecraft_rpc.py` published directly to Discord's IPC
  socket, creating a second connection independent of the newer manager.
- `discord-rpc-bridge.service` and `roaring_vesktop_minecraft_watchd.sh`
  bridged the Vesktop Flatpak socket to a Discord-compatible socket path for
  that standalone client.

The current architecture has one publisher in `core/`; the Minecraft
provider sends activity to that publisher over the private
`roaring-presence.sock`. These legacy files are not installed by the current
installer and should not be enabled alongside the new manager.

The compatibility symlink at `systemd/user/discord-rpc-bridge.service`
exists for old scripts/bookmarks only. After checking that no other tool uses
the bridge, an existing installation can remove it with:

```bash
./install.sh --remove-legacy-bridge
```

The removal option disables the old user unit and removes its installed unit
file. It is intentionally opt-in so an install never stops an existing
session unexpectedly.
