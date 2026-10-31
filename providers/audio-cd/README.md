# Audio-CD provider

This component turns an actual audio CD session into Discord Rich Presence and
provides optional player controls. It is deliberately independent of the
core's Discord IPC implementation.

## Lifecycle and activation

The provider is a per-disc process:

1. a udev `change` event or desktop device action starts
   `roaring-cd-presence /dev/srN`;
2. kernel TOC/CD-Text reads identify the disc;
3. one bounded metadata job can enrich names/artwork;
4. the provider follows playback and drive eject state;
5. on eject or termination it clears activity and exits.

The provider monitors the active disc session. It still checks drive status
while a disc is inserted and observes playback state, because arbitrary CD
players do not all expose one shared event API. The polling is scoped to that
one session and backs off while nothing is playing; there is no all-drive
watcher left running.

## Commands

```bash
roaring-cd-presence /dev/sr1
roaring-cd-presence /dev/sr1 --once --dry-run -v
roaring-cd-autoplay --device /dev/sr1 --album
roaring-cd-autoplay --device /dev/sr1 --track 4
roaring-cd-player --device /dev/sr1
roaring-cd-player --device /dev/sr1 --no-window
```

The control window provides track selection, album playback, transport
buttons, MPRIS2, desktop media-key integration, and a paused preload. Closing
the window leaves the MPRIS service alive only while its disc session exists;
eject ends it.

## Metadata and cache

The kernel supplies the TOC and CD-Text first. `cd-info` is a fallback for
drives that do not provide usable CD-Text through the kernel reader.

MusicBrainz may fill missing artist, album, and track titles. Cover Art Archive
artwork is a separate optional lookup. These two config switches are
independent:

- `lookup_musicbrainz`: permit online release/track metadata lookup;
- `use_cover_art_archive`: additionally fetch front cover artwork.

Disabling cover art must not disable MusicBrainz track names. Per-disc results
are cached under `~/.cache/roaring-presence`. Online work is performed in one
finite job per disc insertion; HTTP retries are bounded, and there is no
20/45/120-second retry timer chain.

## Automatic insertion

Install the component and optionally place the provided udev rule:

```bash
./install.sh --component audio-cd
sudo install -m 644 providers/audio-cd/udev/99-roaring-presence-cd.rules /etc/udev/rules.d/
sudo udevadm control --reload
```

The udev rule asks the user systemd manager to start a per-drive unit only for
an optical drive reporting audio tracks. Root is needed only to install the
rule. Without it, use your desktop's device action or run the command manually.

An optional one-shot login scan catches a disc that was already inserted
before the udev rule/user session became available:

```bash
./install.sh --component audio-cd --enable-login-scan
```

That scan runs once and exits; it is not a polling daemon. It is not enabled
unless requested.

## Dependencies

Linux CD-ROM ioctls are the primary reader. `cd-info` is optional fallback;
`mpv` is used for the built-in playback route; PyQt6 is required only for the
player window. A desktop MPRIS-capable session is required for panel/media-key
integration.

## KDE taskbar and per-app volume

The built-in player advertises the MPRIS service
`org.mpris.MediaPlayer2.roaringcd` with the matching
`roaring-cd-player.desktop` desktop entry. On KDE Plasma 6, the Icons-Only
Task Manager can show media controls and a per-task volume slider in the task
tooltip. In Task Manager settings, the option is named **Show media and volume
controls in tooltip**.

The CD stream is started with mpv's PulseAudio compatibility output and the
application name **Audio CD**. This is intentional: Plasma associates taskbar
volume streams with a task by portal app ID, process ancestry, or application
name. mpv's native PipeWire output only exposed a generic `mpv` node and did
not match the visible Audio CD task. The PulseAudio compatibility path provides
the app name Plasma needs while PipeWire continues to handle the actual audio.

Hover over the Audio CD taskbar icon to access its per-app slider and media
controls. This is separate from the system-wide output volume.
