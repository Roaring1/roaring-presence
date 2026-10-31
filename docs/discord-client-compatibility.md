# Discord desktop client compatibility

## What this project connects to

`roaring-presenced` speaks Discord's documented RPC-over-IPC protocol over a
local Unix-domain socket. It sends a normal RPC handshake containing the
user's Discord Application ID, then publishes activity frames. It does not
use Vencord's plugin APIs, inject code into the client, scan the client's
processes, or require a bot token.

Discord documents these standard Linux/macOS socket locations, in order:

1. `$XDG_RUNTIME_DIR/discord-ipc-N`
2. `$TMPDIR/discord-ipc-N`
3. `$TMP/discord-ipc-N`
4. `$TEMP/discord-ipc-N`
5. `/tmp/discord-ipc-N`

The Linux implementation searches those standard locations and common
package-specific socket paths. It checks socket numbers `0` through `9`.
Configured `ipc_socket_candidates` are tried first, but they do not disable
the built-in fallback locations. The manager only accepts a socket after it
responds to the Discord RPC handshake with `READY`.

Protocol reference: <https://discord.com/developers/docs/topics/rpc>

## Client and package notes

| Client / packaging | Discovery | Notes |
| --- | --- | --- |
| Official Discord desktop, native Linux package | Standard XDG/temp socket | No Vencord or plugin required. This is the normal target path; a live smoke test on each distro remains part of release validation. |
| Official Discord Flatpak | App-scoped runtime socket | The Flatpak wrapper uses a sandbox-specific socket location. The host-side path is included in discovery. Flatpak game-process scanning limitations are separate from an external publisher sending RPC to the client. |
| Vesktop, native package | Standard or app-scoped socket | Enable the client's RPC/arRPC integration if it is disabled. |
| Vesktop Flatpak | Vesktop's Flatpak runtime socket | Maintainer-tested with the Flatpak Vesktop setup on one Linux desktop. Its own process-scanning/game-detection limitations do not describe this external provider's IPC publishing path. |
| Discord Snap | Snap-scoped runtime socket | Candidate paths are included, but this package path is not yet verified in a live test. |
| Other Discord-compatible desktop clients | Standard path or user-configured path | Expected to work when the client implements compatible RPC-over-Unix-socket and returns the normal `READY` handshake. Not every alternative client has been tested. |

This repository currently targets **Linux desktops with Unix sockets and a
systemd user session**. The audio-CD provider additionally needs Linux
CD-ROM ioctls and udev for automatic insertion activation. This is not a
claim of Windows, macOS, browser-only, or mobile support.

## First-run checklist

1. Install and launch a Discord-compatible desktop client. A web browser tab
   or the mobile app cannot provide the Linux Unix socket used here.
2. If using an alternative client, enable its local RPC/arRPC integration in
   that client's settings.
3. Create an application in the
   [Discord Developer Portal](https://discord.com/developers/applications) and
   copy its **Application ID** into `client_id` in
   `~/.config/roaring-presence/config.json`. This is a public ID, not a bot
   token, account token, or password.
4. Run `roaring-presence-doctor`. It reports the exact discovered socket paths.
5. Start an activity provider. `roaring-presence-doctor --query-manager` is
   available when you explicitly want to contact the manager; that can activate
   its systemd socket.

Discord's activity/privacy settings still control what other people can see.

## Troubleshooting a missing IPC socket

Start the desktop client first, then run:

```bash
roaring-presence-doctor
```

The doctor reports existing Unix socket nodes rather than merely matching
filenames. If it finds no socket:

- Confirm that the desktop client is running, not just the browser version.
- Check the client's settings for local RPC/arRPC support.
- Inspect `$XDG_RUNTIME_DIR`, `$TMPDIR`, `$TMP`, and `$TEMP` for a
  `discord-ipc-0` through `discord-ipc-9` socket.
- For a client with a nonstandard location, add its path pattern to
  `ipc_socket_candidates`; preserve the `{i}` placeholder. Custom entries are
  preferences, not a replacement for built-in discovery.
- If several desktop clients are running, put the preferred client's socket
  path first. The first socket that completes the RPC handshake is used.

No Flatpak overrides, global symlinks, root permissions, or Discord client
modifications are installed automatically by this project. Sandboxed clients
may expose their socket differently; use the client/package's own documented
permissions and do not make broad filesystem grants just to silence a warning.
