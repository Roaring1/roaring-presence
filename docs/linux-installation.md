# Linux installation and dependencies

`roaring-presence` targets Linux desktops with a user systemd manager, Unix
sockets, and a session D-Bus. The built-in CD player uses Linux CD-ROM ioctls,
mpv, PyQt6, and QtDBus.

## Choose an install profile

```bash
# Standalone audio-CD player; no Discord required
./install.sh

# Same player plus Discord Rich Presence
./install.sh --component audio-cd
```

The installer writes commands to `~/.local/bin`, installs only the selected
user-level units, preserves existing configuration, and never installs OS
packages or requests root permissions. Desktop entries and service files use
absolute paths and do not depend on `PATH`.

Start a session manually with a disc inserted:

```bash
# Standalone player
~/.local/bin/roaring-cd-presence --player-only /dev/sr0

# Same player with Discord publishing
~/.local/bin/roaring-cd-presence /dev/sr0
```

Automatic insertion is optional. Install exactly one rule:

```bash
# Standalone player
sudo install -m 644 providers/audio-cd/udev/99-roaring-cd-player.rules /etc/udev/rules.d/

# OR player plus Discord presence
sudo install -m 644 providers/audio-cd/udev/99-roaring-presence-cd.rules /etc/udev/rules.d/

sudo udevadm control --reload
```

Do not install both rules for the same drive. The two user units conflict per
drive, preventing duplicate session owners. Removing the chosen rule later
only requires deleting that file from `/etc/udev/rules.d/` and reloading udev.
A one-shot login scan is also available with
`./install.sh --enable-login-scan`.

## Dependencies by feature

| Package / command | Purpose | Required? |
| --- | --- | --- |
| `mpv` with CDDA enabled | Audio-CD playback | Required |
| `eject` | Open the optical drive tray from the player | Required for the Eject button |
| Python 3.10+ | Session provider and tools | Required |
| PyQt6 + QtDBus | Player window and MPRIS2 controls | Required for the built-in CD player |
| Linux user systemd | Per-disc session units | Required for automatic service integration |
| Session D-Bus | KDE/taskbar MPRIS2 integration | Required for MPRIS2 controls |
| `cd-info` | Fallback disc reader | Optional; kernel ioctls are primary |
| Pillow | Artwork tools | Optional; only needed for asset utilities |

## Package-manager examples

Package names can vary by distribution release.

### Fedora, Nobara and related DNF systems

```bash
sudo dnf install mpv python3-pyqt6 eject
```

Optional artwork tools:

```bash
sudo dnf install python3-pillow
```

The kernel reader works without `cd-info`; install the distribution's libcdio
package only when you want that fallback.

### Ubuntu and Debian-family systems

```bash
sudo apt install mpv python3-pyqt6 eject
```

Optional metadata fallback and artwork tools:

```bash
sudo apt install libcdio-utils python3-pil
```

### Arch Linux

```bash
sudo pacman -S mpv python-pyqt6 util-linux
```

Optional metadata fallback and artwork tools:

```bash
sudo pacman -S libcdio python-pillow
```

## Discord setup (only for `audio-cd`)

Create or select an application in the [Discord Developer Portal](https://discord.com/developers/applications),
copy its **Application ID**, and place it in
`~/.config/roaring-presence/config.json` as `client_id`. This is a public
identifier, not a bot token. Keep a compatible desktop Discord client running
and run:

```bash
~/.local/bin/roaring-presence-doctor --component audio-cd
```

The provider talks to the local shared core. The core is the only component
that owns a Discord IPC connection. See
[Discord client compatibility](discord-client-compatibility.md).

## Upgrade and diagnostics

A Git checkout installation creates `roaring-presence-update`, pinned to the
same repository, branch, and component profile used at install time:

```bash
roaring-presence-update --check
roaring-presence-update
```

The updater refuses to overwrite local edits or update across divergent
history. It verifies fetched code in a temporary worktree, runs tests,
reinstalls the selected profile, and refreshes relevant user services.
Existing configuration is preserved.

Use the component-filtered doctor and logs:

```bash
roaring-presence-doctor --component cd-player
roaring-presence-doctor --component audio-cd
journalctl --user -u 'roaring-cd-player@*' -f
journalctl --user -u 'roaring-cd-presence@*' -f
tail -f "${XDG_CACHE_HOME:-$HOME/.cache}/roaring-presence/player.log"
```

This project does not claim support for Windows, macOS, non-systemd Linux
distributions, browser-only Discord, mobile clients, or every sandboxed
Discord client. Test each client/package combination before describing it as
supported.
