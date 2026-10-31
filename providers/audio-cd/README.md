# Audio-CD component

The CD player and Discord publisher are separate features that share one
CD-session engine. You can install the player by itself; the Discord
integration is optional.

## Standalone player

The `cd-player` install profile detects inserted audio discs, reads the disc's
track table and CD-Text, offers the player window, and provides MPRIS2/media
keys. It does not install or contact the Discord core, does not need a Discord
Application ID, and does not require a running Discord client.

```bash
./install.sh --component cd-player
```

For automatic insertion, install the matching udev rule once (system-wide):

```bash
sudo install -m 644 providers/audio-cd/udev/99-roaring-cd-player.rules /etc/udev/rules.d/
sudo udevadm control --reload
```

Without the rule, start a session explicitly:

```bash
~/.local/bin/roaring-cd-session /dev/sr0
```

The optional login catch-up scan is a one-shot service, not a resident
polling daemon:

```bash
./install.sh --component cd-player --enable-login-scan
```

## Optional Discord Rich Presence

Choose `audio-cd` (or its clearer alias `discord-cd`) to add the Discord
publisher. This installs the small shared core and reuses the same CD player;
playback, MPRIS, metadata, and eject handling are not duplicated.

```bash
./install.sh --component audio-cd
```

A Discord Application ID is required for publishing. Configure it in
`~/.config/roaring-presence/config.json` as `client_id`. The ID is public; it
is not a bot token or password. A compatible desktop Discord client must be
running and expose its local RPC socket.

The `audio-cd` profile installs a separate udev rule which starts the
Discord-enabled provider. Do not install both CD udev rules at once; choose
one session mode. If you want both standalone playback and Discord presence,
use `audio-cd`—it already includes the player.

## Lifecycle and detection

Both modes use the same per-disc process:

1. a udev change event or explicit command starts one session for `/dev/srN`;
2. the kernel supplies the table of contents and CD-Text;
3. an optional bounded metadata job enriches track names and cover art;
4. the player follows playback and exposes MPRIS2 controls;
5. eject is detected and the process exits cleanly.

The player-only mode never connects to the Discord manager socket. Presence
mode publishes through the shared core; providers never connect to Discord
directly. Neither mode leaves a global drive-polling daemon running.

## Metadata and cache

MusicBrainz may fill missing artist, album, and track titles. Cover Art Archive
artwork is a separate optional lookup. The two config switches are independent:

- `lookup_musicbrainz`: permit online release/track metadata lookup;
- `use_cover_art_archive`: additionally fetch front cover artwork.

The Linux kernel's TOC/CD-Text is read first. Online metadata work is bounded
and performed once per disc insertion; results are cached under
`$XDG_CACHE_HOME/roaring-presence` (or `~/.cache/roaring-presence` when
`XDG_CACHE_HOME` is unset). The player remains usable offline, with local
CD-Text or generic track labels.

## Dependencies

`mpv` is required for playback. PyQt6 with QtDBus provides the full player
window and MPRIS service; the provider can fall back to a desktop dialog when
the window dependencies are absent. `cd-info` is an optional fallback for
reading disc metadata. `psutil` is required for process and playback discovery.
A graphical session is needed for the player window; MPRIS-only operation can
run without a window.

## KDE taskbar and per-app volume

The player advertises `org.mpris.MediaPlayer2.roaringcd` with the matching
`roaring-cd-player.desktop` desktop entry. On KDE Plasma 6, the Icons-Only Task
Manager can show media controls and a per-task volume slider in the task
tooltip. In Task Manager settings, enable **Show media and volume controls in
tooltip**.

The CD stream uses mpv's PulseAudio compatibility output and the application
name **Audio CD** when that output backend is available. On PipeWire desktops,
PipeWire-Pulse provides the stream identity Plasma needs while PipeWire handles
the actual audio. Other desktops use their own MPRIS/media controls; the KDE
volume tooltip is a Plasma-specific enhancement.
