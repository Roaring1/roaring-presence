# Audio-CD component

The audio-CD component detects an inserted disc, identifies its tracks, opens
a small player, and optionally publishes the song currently playing to
Discord. Playback and metadata work without Discord.

## Install and start

The standalone player is the default profile:

```bash
./install.sh --component cd-player
```

With a disc inserted, start it manually (replace `sr0` with your drive):

```bash
~/.local/bin/roaring-cd-presence --player-only /dev/sr0
```

To add Discord Rich Presence for the same session:

```bash
./install.sh --component audio-cd
```

Set `client_id` in `~/.config/roaring-presence/config.json` and keep a
compatible Discord desktop client running. The provider sends activity to the
shared local core; it does not create another Discord connection.

Automatic start on insertion is optional. Install exactly one udev rule,
matching the profile you use:

```bash
# Standalone player
sudo install -m 644 providers/audio-cd/udev/99-roaring-cd-player.rules /etc/udev/rules.d/

# OR player plus Discord presence
sudo install -m 644 providers/audio-cd/udev/99-roaring-presence-cd.rules /etc/udev/rules.d/

sudo udevadm control --reload
```

Do not install both rules for the same drive. The per-drive user units also
conflict, so only one session mode can own a disc at a time. An optional
one-shot login scan can start a session for a disc that was already inserted.

## The session

One per-disc user service owns the session and starts one player process. The
player owns mpv, its IPC connection, the window, drive-eject detection, and
its MPRIS2 registration. There are no autoplay dialogs, paused preloads,
detached eject watchdogs, or transient `systemd-run` scopes.

The window has a track list, play/pause, previous/next, and eject controls.
Select a track or start the album from the window. The visible next-track
button remains the straightforward way to skip a song. KDE's taskbar and
media controls use the player's MPRIS2 interface; no global keyboard listener
or extra media-key service is installed.

Closing the player closes the session: mpv is stopped and reaped, the MPRIS
name is released, and the provider clears the Discord activity. Ejecting the
disc has the same cleanup effect. A paused or idle player never appears as
listening on Discord. Presence appears only after mpv confirms active
playback, clears on pause or stop, and returns when playback resumes.

Each drive gets its own mpv IPC socket under `$XDG_RUNTIME_DIR`, so a second
drive cannot accidentally report the first drive's track. The old default
socket names are recognized during migration. An explicitly custom
`cd.mpv_ipc_socket` path is still honored.

## Metadata

The Linux kernel supplies the table of contents and CD-Text. MusicBrainz can
fill missing artist, album, and track names; Cover Art Archive artwork is a
separate optional lookup. Results are cached under
`$XDG_CACHE_HOME/roaring-presence` (or `~/.cache/roaring-presence`). Local
CD-Text and generic track labels remain available offline.

- `lookup_musicbrainz`: permit online release and track metadata lookup.
- `use_cover_art_archive`: fetch front-cover artwork as a separate lookup.

## Dependencies

The built-in player requires `mpv` with CDDA support, the `eject` utility,
Python 3.10+, PyQt6, QtDBus, a graphical session, and a session D-Bus.
`cd-info` is an optional fallback for disc metadata; the kernel reader is
primary.

## KDE taskbar controls

The player registers `org.mpris.MediaPlayer2.roaringcd` and uses the matching
`roaring-cd-player.desktop` identity. KDE Plasma's task manager can display
media controls and the per-task volume tooltip when **Show media and volume
controls in tooltip** is enabled.

When mpv offers its PulseAudio compatibility output, the player selects it
with the application name **Audio CD**. PipeWire-Pulse exposes that identity
to Plasma while PipeWire handles audio. Other MPRIS-capable desktops can use
the same playback controls; the volume tooltip is Plasma-specific.
