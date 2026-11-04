# roaring-presence

**A modular Linux audio-CD player with optional Discord Rich Presence.**
Install just the CD player, or add the Discord publisher, Minecraft activity,
and generic artwork tools when you need them. The standalone player does not
require Discord, a Discord Application ID, or the shared presence daemon.

This repository is a set of installable components, not one opaque desktop
daemon:

## Quick start

On Fedora/Nobara, install the base audio-CD dependencies first. Add
`python3-pyqt6` for the full graphical player window and MPRIS controls:

```bash
sudo dnf install mpv python3-psutil python3-pyqt6

git clone https://github.com/Roaring1/roaring-presence.git
cd roaring-presence
./install.sh --component cd-player
```

With a disc inserted, start it manually (replace `sr0` with your drive):

```bash
~/.local/bin/roaring-cd-session /dev/sr0
```

For automatic start on disc insertion, install the optional udev rule printed
by the installer; it requires one explicit, system-wide administrator action.
Other distributions and package names are covered in
[Linux installation](docs/linux-installation.md).

To add Discord Rich Presence later, install the `audio-cd` profile and set the
Discord Application ID in your user config. The existing CD player remains the
same feature; Discord publishing is just an additional component.


| Component | Job | When it runs |
| --- | --- | --- |
| **CD player** | Disc detection, metadata, playback controls, MPRIS/media keys and eject cleanup | Started by an optical-disc event or explicit command; lives for that disc session |
| **Discord CD** | Publishes the same CD session as Discord Rich Presence through the shared core | Optional companion to the CD player; no duplicate player process |
| **Core** | One Discord IPC connection and provider-priority arbitration | Socket-activated; exits shortly after its last provider leaves |
| **Minecraft** | Detect a game session and publish instance/server/world details | Optional launcher-triggered provider; watches that one process |
| **Assets** | Prepare arbitrary images and generate optional built-in artwork | One-shot local commands; no service |

The core can be in the background while it is doing useful work. The distinction
is that it has a defined job and lifecycle: the socket is passive, providers
connect when their source event occurs, and the manager releases its Discord
connection and exits when no providers remain. There is no generic scan-everything
watchdog installed by default.

## Pick the parts you want

The default install is the standalone audio-CD player:

```bash
./install.sh
```

It does not install or contact Discord. To add Discord Rich Presence for the
same CD playback session, choose:

```bash
./install.sh --component audio-cd
# equivalent, more explicit name:
./install.sh --component discord-cd
```

Other parts stay opt-in:

```bash
./install.sh --component core
./install.sh --component minecraft
./install.sh --component assets
./install.sh --component all
```

The Discord CD and Minecraft providers include the small core automatically.
Components can be combined by repeating `--component`. See
`./install.sh --help` for all options. The installer uses `~/.local/bin`,
preserves existing configuration, and does not use sudo. A separate udev
rule is optional for automatic disc insertion.

For supported package names and setup details, see
[Linux installation](docs/linux-installation.md).

For Discord-enabled profiles, the installer:
- installs only explicit executable entry points (never a broad `bin/*` glob);
- preserves an existing user config rather than overwriting it;
- enables only the core's passive systemd user socket;
- does not enable the Minecraft provider or a periodic process watcher;
- does not install the obsolete standalone Discord RPC bridge.

Only Discord-enabled components need a Discord Application ID. Open
[Discord Developer Portal](https://discord.com/developers/applications), create
or choose an application, and copy its **Application ID** into
`~/.config/roaring-presence/config.json` as `client_id`. It is a public
application identifier, not a bot token or password.

Then run the read-only setup check:

```bash
~/.local/bin/roaring-presence-doctor
~/.local/bin/roaring-presence-doctor --json
```

It checks JSON configuration, the application ID, Discord IPC discovery,
optional dependencies, asset keys, and the manager socket path. By default it
does not connect to that socket, so it cannot trigger systemd activation. Use
`roaring-presence-doctor --query-manager` only when you explicitly want a live
status request; connecting may activate the manager socket.

## Discord client compatibility

This project is a local Discord RPC client. It sends activity to a running
Discord-compatible desktop client over a Unix socket; it does not inspect how
the client is packaged and does not require Vencord. Native installs normally
use the standard socket in `$XDG_RUNTIME_DIR` (or the configured temp directory).
The core also checks common Flatpak and Snap socket layouts. User-configured
paths are tried first, and the built-in fallback list is still searched.

The Discord client must be running and expose its local RPC endpoint. Some
alternative clients require their RPC/arRPC integration to be enabled in the
client's own settings. A browser-only Discord tab is not a local desktop IPC
server. See [the client compatibility guide](docs/discord-client-compatibility.md)
for exact support boundaries and diagnostics.

## Components

### Core publisher

`core/` owns the one Discord Rich Presence IPC connection. Providers send
newline-delimited JSON over the private Unix socket
`$XDG_RUNTIME_DIR/roaring-presence.sock`; providers never connect to Discord
directly.

The manager arbitrates live activities by priority. The bundled defaults put
audio CD above Minecraft, so a disc session wins while it is present and the
Minecraft activity becomes visible again when the disc provider disconnects.
The socket has mode `0600`; it is local to the user.

The manager speaks Discord's standard local RPC-over-IPC protocol. It does not
use Vencord APIs, a browser extension, or a game-scanning plugin. Any compatible
Linux desktop client that exposes the local IPC socket can receive provider
activities. See [Discord client compatibility](docs/discord-client-compatibility.md)
for native, Flatpak, Vesktop, Snap, and troubleshooting notes.

The systemd socket can remain enabled. That is not the same as keeping a
polling daemon resident: systemd holds the listening socket and starts the
manager when a provider connects. The manager exits after the final provider
disconnects (one second by default), clearing activity and closing its Discord
connection first.

See [core documentation](core/README.md) and
[the provider protocol](docs/architecture.md).

### Audio-CD provider

`providers/audio-cd/` owns the shared audio-CD session engine. The
`cd-player` install profile uses it without Discord; `audio-cd` adds the
optional Rich Presence publisher. It handles audio CDs from insertion to eject:

- reads the table of contents and CD-Text from the Linux kernel first, with
  `cd-info` as a fallback;
- computes the MusicBrainz Disc ID and can fill missing artist, album, and
  track titles from MusicBrainz;
- fetches front artwork from the Cover Art Archive when enabled;
- caches resolved metadata and artwork locally per disc;
- follows playback, publishes the active track and progress, and clears
  activity/stops playback on eject;
- provides the optional PyQt6 player window, MPRIS2 controls, media keys,
  autoplay choice, and paused preload.

MusicBrainz metadata lookup and Cover Art Archive art lookup are separate
settings. Turning off `use_cover_art_archive` does not turn off MusicBrainz
track-title lookup.

The provider is session work, not a system-wide watcher. A udev rule can start
it on an audio-disc insertion event; KDE actions or a direct command can do
the same. A one-shot catch-up scan is optional:

```bash
./install.sh --component cd-player --enable-login-scan
./install.sh --component audio-cd --enable-login-scan
```

Automatic udev activation needs one root-owned rule installation, printed by
the installer. Without it, start the provider from your desktop's device
action or run:

```bash
~/.local/bin/roaring-cd-session /dev/sr1   # no Discord dependency
~/.local/bin/roaring-cd-presence /dev/sr1  # publishes to Discord
```

See [audio-CD documentation](providers/audio-cd/README.md).

### Minecraft provider

`providers/minecraft/` publishes a session for Minecraft Java or Bedrock.
It can report the edition, version, mod loader, launcher instance, multiplayer
server, or single-player world name when those details are available.

Start it from a launcher event (or manually):

```bash
systemctl --user start --no-block roaring-minecraft-presence.service
```

The bundled user unit has a short 30-second launch-detection window for
pre-launch hooks. Once it identifies the game, it attaches to that process:
on modern Linux it waits on a **pidfd** for process exit and uses **inotify**
for instance-log changes. It does not rescan the entire process table every
few seconds for the whole game session. If pidfd is unavailable, it falls
back to checking only that process's start identity at a configurable
interval.

For a launcher that can provide the actual Java PID, use
`roaring-minecraft-presence --pid PID` to avoid broad discovery entirely.
For a one-shot payload test:

```bash
~/.local/bin/roaring-minecraft-presence --demo --once --dry-run
```

See [Minecraft documentation](providers/minecraft/README.md).

### Asset tools

`tools/assets/` contains two local, one-shot tools:

- `roaring-presence-assets` converts any supported source image into a
  square PNG and emits a manifest. Give images friendly keys or let their
  filenames supply the keys.
- `roaring-presence-art.py` generates the optional roaring-presence-themed
  app icon and sample activity art. It can change output directory, size, and
  key prefix, and writes a manifest with the upload names and config mapping.

Example for arbitrary artwork:

```bash
roaring-presence-assets --output-dir ./my-assets --fit contain \
  "studio-logo=~/Pictures/logo.webp" \
  "game-cover=~/Pictures/cover.jpg" \
  ~/Pictures/brand-mark.png
```

This produces `studio-logo.png`, `game-cover.png`,
`brand-mark.png`, and `manifest.json`. To crop instead of letterbox:

```bash
roaring-presence-assets --fit cover --overwrite \
  "wide-banner=~/Pictures/banner.png"
```

The built-in artwork generator is independently configurable:

```bash
roaring-presence-art.py --output-dir ~/Pictures/my-discord-assets \
  --size 1024 --key-prefix my-app
```

**Upload is intentionally generic, not account-bound.** The tools prepare PNGs
and tell you the matching asset keys; they do not store Discord credentials or
pretend to upload through an undocumented API. Open your application's
**Rich Presence → Art Assets** page in the Developer Portal, upload the PNGs,
and use the exact keys from `manifest.json`. Use the generated `config.assets`
mapping in `config.json` if you changed the keys.

The asset packer requires Pillow. See [asset-tool documentation](tools/assets/README.md).

## Configuration

Discord-enabled profiles copy `config/config.sample.json` to
`~/.config/roaring-presence/config.json` only if that file does not exist.
The standalone CD player needs no config. Edit your user file; reinstalling
will never overwrite it.

The important top-level settings are:

| Setting | Purpose |
| --- | --- |
| `client_id` | Your Discord application's public Application ID |
| `ipc_socket_candidates` | Preferred local Discord IPC socket paths; portable built-in fallbacks are always tried |
| `idle_exit_seconds` | Grace period before the empty manager exits |
| `priorities` | Relative priority of each provider |
| `assets` | Discord Rich Presence asset keys |
| `cd` | Audio-CD discovery, metadata, player and playback settings |
| `minecraft` | Minecraft process/session details and fallback interval |

See the sample config for all CD and Minecraft options. Environment variables
such as `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_RUNTIME_DIR` and
`HOME` are respected where applicable.

## Requirements

The project targets Linux desktops with user systemd and Unix sockets.

| Feature | Required | Optional / fallback |
| --- | --- | --- |
| Core | Python 3.10+; a compatible Discord desktop client exposing local RPC/IPC; Linux user systemd | Known native, Flatpak, and Snap socket paths are auto-discovered; custom paths can be added |
| Audio-CD detection | Linux optical drive and kernel CD-ROM ioctls | `cd-info` fallback |
| CD playback | `mpv` with CDDA support | Other desktop CD players can be used outside the built-in UI |
| CD session tracking | `psutil` for active-player discovery, track and progress tracking | Required for reliable session state and autoplay avoidance |
| CD player window | PyQt6, QtDBus and a graphical session | kdialog/zenity prompt and command-line playback |
| CD metadata | Network access for MusicBrainz/CAA | Cached metadata and local CD-Text work offline |
| Automatic disc insert | udev rule installed once as root | KDE device action or manual command |
| Minecraft session | Java/Bedrock client | psutil is optional; Linux `/proc` fallback is built in |
| Asset tools | Python and Pillow | None |

No telemetry is sent. Audio-CD metadata lookup contacts MusicBrainz and, when
enabled, the Cover Art Archive. Presence is sent to the local Discord/Vesktop
IPC endpoint; the application does not need a Discord bot token.

## Repository map

```text
core/
  bin/                  manager and doctor
  systemd/user/         passive socket activation
providers/
  audio-cd/
    bin/                CD provider, player, autoplay, catch-up scan
    systemd/user/       disc-session units
    udev/               optional insert-event rule
    desktop/            CD player desktop entry
  minecraft/
    bin/                Minecraft session provider
    systemd/user/       launcher-triggered unit
tools/
  assets/bin/           generic image packer and built-in artwork generator
config/                 shared example configuration
legacy/                 superseded direct-RPC bridge, retained for migration
docs/                   architecture, client compatibility, and hardware notes
tests/                  offline regression tests
```

The former top-level `bin/`, `systemd/user/`, `udev/`, and `desktop/`
paths remain as compatibility symlinks for existing scripts and bookmarks.
New development should use the component directories.

## Development checks

Run the offline regression suite from the repository root:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile \
  core/bin/roaring-presenced \
  core/bin/roaring-presence-doctor \
  providers/audio-cd/bin/roaring-cd-presence \
  providers/audio-cd/bin/roaring-cd-autoplay \
  providers/audio-cd/bin/roaring-cd-player \
  providers/audio-cd/bin/roaring-cd-session \
  providers/audio-cd/bin/cd_paths.py \
  providers/minecraft/bin/roaring-minecraft-presence \
  tools/assets/bin/roaring-presence-art.py \
  tools/assets/bin/roaring-presence-assets
bash -n install.sh
```

The tests are hardware-independent: they use synthetic Discord payloads,
temporary image files, temporary log directories, and a disposable child
process for the pidfd lifecycle test. They do not need a CD in the drive,
a running Minecraft game, or a live Discord session. GitHub Actions runs the
same checks on pushes and pull requests.

## Updating and troubleshooting

A Git checkout install creates `roaring-presence-update`. It checks the
configured GitHub branch, refuses to overwrite local edits or a diverged
checkout, tests the candidate commit in a temporary worktree, then reinstalls
the selected profile and refreshes active provider processes. Use:

```bash
~/.local/bin/roaring-presence-update --check
~/.local/bin/roaring-presence-update
```

Start diagnostics for the feature you use:

```bash
~/.local/bin/roaring-presence-doctor --component cd-player
~/.local/bin/roaring-presence-doctor --component audio-cd
journalctl --user -u roaring-presenced -f
journalctl --user -u 'roaring-cd-presence@*' -f
```

Useful CD diagnostics:

```bash
~/.local/bin/roaring-cd-presence /dev/sr1 --once --dry-run -v
journalctl --user -u 'roaring-cd-presence@*' -f
tail -f "${XDG_CACHE_HOME:-$HOME/.cache}/roaring-presence/autoplay.log"
```

Useful Minecraft diagnostics:

```bash
~/.local/bin/roaring-minecraft-presence --demo --once --dry-run
journalctl --user -u roaring-minecraft-presence -f
```

If the Discord socket is missing, start your desktop Discord client and run
`roaring-presence-doctor`. The manager checks the standard XDG/temp paths and
common sandbox locations. Add a custom path to `ipc_socket_candidates` only if
your client uses a nonstandard socket. See the compatibility guide if no
socket is found. If no activity appears, check the
manager endpoint with `roaring-presence-doctor`, optionally query it with
`roaring-presence-doctor --query-manager`, and verify your Application ID.
For CD images, confirm the asset key in the Developer Portal exactly matches
the key in config. Dynamic Cover Art Archive artwork is separate from your
application's uploaded asset keys.

## Legacy files

`legacy/` retains the old direct-Discord Minecraft RPC client and the
Vesktop-to-Prism `socat` bridge for reference. They are not installed by the
current installer. The core manager now owns Discord IPC and supports multiple
providers on one connection. After verifying that nothing else uses the old
bridge, remove an enabled copy with:

```bash
./install.sh --remove-legacy-bridge
```

See [architecture and lifecycle notes](docs/architecture.md) for the design.


## Project information

- [MIT License](LICENSE)
- [Changelog](CHANGELOG.md)
- [Support and supported scope](SUPPORT.md)
- [Maintainer release procedure](docs/releasing.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

The MIT License covers original project code and documentation in this
repository. External system packages and compatible desktop clients retain
their own licenses and terms; see [third-party notices](THIRD_PARTY_NOTICES.md).
