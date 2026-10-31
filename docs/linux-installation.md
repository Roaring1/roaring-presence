# Linux installation and dependencies

`roaring-presence` is currently a Linux desktop project. The CD session uses
Linux CD-ROM ioctls, a user systemd manager, and Unix sockets. It is designed
for common systemd desktops rather than a specific desktop shell. The player
window is optional; MPRIS/media keys depend on a session D-Bus and an MPRIS-
capable desktop.

## Choose an install profile

```bash
# Standalone audio-CD player; no Discord required
./install.sh

# Same player plus Discord Rich Presence
./install.sh --component audio-cd

# Explicitly named alias for the same integration
./install.sh --component discord-cd
```

The installer places executable files in `~/.local/bin`, installs only the
selected user-level systemd units, preserves user configuration, and does not
install operating-system packages or request root permissions. It never
changes Flatpak/Snap permissions. To make command names available in a shell,
add `~/.local/bin` to that shell's PATH; the installed desktop launcher and
systemd units use absolute paths and do not rely on PATH.

The player starts manually without a udev rule:

```bash
~/.local/bin/roaring-cd-session /dev/sr0
```

Automatic disc insertion is an optional integration. Choose exactly one rule:

```bash
# Standalone player
sudo install -m 644 providers/audio-cd/udev/99-roaring-cd-player.rules /etc/udev/rules.d/

# OR Discord-enabled player + publisher
sudo install -m 644 providers/audio-cd/udev/99-roaring-presence-cd.rules /etc/udev/rules.d/

sudo udevadm control --reload
```

Do not install both rules: both match the same inserted disc. The two user
units also declare a per-drive conflict, so accidental dual activation cannot
leave two CD-session engines running. Removing the rule later is as simple as
removing the chosen file from `/etc/udev/rules.d/` and reloading udev.

## Dependencies by feature

| Package / command | Purpose | Required? |
| --- | --- | --- |
| `mpv` with CDDA enabled | Built-in CD audio playback | Required for built-in playback |
| `psutil` | Disc-player process discovery and track/progress observation | Required for reliable session tracking |
| Python 3.10+ | Providers and tools | Required |
| user `systemd` and `systemctl` | Per-disc user services and core socket activation | Required for automatic service integration |
| PyQt6 + QtDBus | Full player UI and MPRIS/media-key service | Recommended; optional prompt/player fallbacks remain |
| `kdialog` or `zenity` | Dialog fallback without the Qt window | Optional; desktop-dependent |
| `cd-info` | Fallback disc reader | Optional; kernel ioctl reader is primary |
| `psutil` | Identify active CDDA players, follow track/progress, and avoid duplicate autoplay | Required for reliable session tracking |
| Pillow | Image preparation tools | Optional; only needed for asset utilities |

## Package-manager examples

Package names vary by release. The commands below cover the current names
checked for Fedora, Ubuntu, and Arch Linux; use your distribution's package
search if a package has been renamed or split.

### Fedora, Nobara and related DNF systems

Base standalone playback and tracking:

```bash
sudo dnf install mpv python3-psutil
```

Recommended full player UI and MPRIS/media-key integration:

```bash
sudo dnf install python3-pyqt6
```

For the optional image tools:

```bash
sudo dnf install python3-pillow
```

For the optional `cd-info` fallback, check whether your release splits the
utility into an additional libcdio package. The kernel reader does not require
it. Fedora publishes `mpv`, `python3-pyqt6`, `python3-psutil`, and
`python3-pillow` as packages. [Fedora package references](#package-references)

### Ubuntu and Debian-family systems

Base standalone playback and tracking:

```bash
sudo apt install mpv python3-psutil
```

Recommended full player UI and MPRIS/media-key integration:

```bash
sudo apt install python3-pyqt6
```

Optional image utilities and `cd-info` fallback:

```bash
sudo apt install python3-pil libcdio-utils
```

On Ubuntu, `cd-info` is provided by `libcdio-utils`; PyQt6 and psutil are
separate Python packages. [Ubuntu package references](#package-references)

### Arch Linux

Base standalone playback and tracking:

```bash
sudo pacman -S mpv python-psutil libcdio
```

Recommended full player UI and MPRIS/media-key integration:

```bash
sudo pacman -S python-pyqt6
```

Optional image utilities:

```bash
sudo pacman -S python-pillow
```

Arch's `libcdio` package includes `cd-info`. [Arch package references](#package-references)

## Discord setup (only for `audio-cd` / `discord-cd`)

Create or select an application in the [Discord Developer Portal](https://discord.com/developers/applications),
copy its **Application ID**, and place it in
`~/.config/roaring-presence/config.json` as `client_id`. This is a public
application identifier, not a bot token. Start a compatible Discord desktop
client and run:

```bash
~/.local/bin/roaring-presence-doctor --component audio-cd
```

The integration speaks Discord's standard local RPC-over-IPC protocol. It
does not require Vencord, but the client must expose the local RPC socket.
See [client compatibility](discord-client-compatibility.md).

## Upgrade and diagnostics

A Git checkout installation creates `roaring-presence-update`, pinned to the
same repository, branch and component profile used at install time:

```bash
roaring-presence-update --check
roaring-presence-update
```

The updater refuses to overwrite local edits or update across a divergent
history. It verifies fetched code in a temporary worktree before updating the
checkout, runs tests, reinstalls the selected profile, and refreshes active
provider sessions. The installer does not modify your existing config.

Use the component-filtered doctor:

```bash
roaring-presence-doctor --component cd-player
roaring-presence-doctor --component audio-cd
```

## Package references

- Fedora: `mpv`, [python3-pyqt6](https://packages.fedoraproject.org/pkgs/python-pyqt6/python3-pyqt6/), [python3-psutil](https://packages.fedoraproject.org/pkgs/python-psutil/python3-psutil/), and [python3-pillow](https://packages.fedoraproject.org/pkgs/python-pillow/python3-pillow/).
- Ubuntu: [python3-pyqt6](https://packages.ubuntu.com/python3-pyqt6), python3-psutil, python3-pil, and [libcdio-utils / cd-info](https://manpages.ubuntu.com/manpages/noble/man1/cd-info.1.html).
- Arch: [mpv](https://archlinux.org/packages/extra/x86_64/mpv/), [python-pyqt6](https://archlinux.org/packages/extra/x86_64/python-pyqt6/), [python-psutil](https://archlinux.org/packages/extra/x86_64/python-psutil/), [python-pillow](https://archlinux.org/packages/extra/x86_64/python-pillow/), and [libcdio (includes cd-info)](https://archlinux.org/packages/extra/x86_64/libcdio/files/).

This guide does not claim support for Windows, macOS, browser-only Discord,
mobile clients, non-systemd Linux distributions, or every sandboxed Discord
client. Client-specific IPC layouts should be independently tested before
being described as supported.
