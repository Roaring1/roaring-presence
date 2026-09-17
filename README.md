# roaring-presence

A small Discord Rich Presence stack for Linux. Its main job: when you put an
audio CD in the drive, Discord shows what is actually spinning — artist, track,
album, cover art, and a real progress bar — the way a CD player would report it.

No cloud service, no polling of a music API for "now playing". The disc itself
is the source of truth: the table of contents is read straight from the kernel,
and the position comes from the player over an IPC socket.

```
Listening to Slipknot
Adderall
The End, So Far · Track 1 of 12
[cover art]  0:55 ──────────  5:41
```

## Pieces

| Path | What it does |
| --- | --- |
| `bin/roaring-presenced` | The manager. Owns the single Discord IPC connection and publishes whichever provider has the highest priority. Socket-activated. |
| `bin/roaring-cd-presence` | The audio-CD provider. Reads the disc, resolves metadata, watches playback, publishes activity. One instance per drive. |
| `bin/roaring-cd-autoplay` | Minimal "disc inserted — what now?" prompt: full album, a single track, or nothing. |
| `bin/roaring-presence-scan` | Picks up drives that already had a disc at login. |
| `bin/roaring-minecraft-presence`, `bin/roaring_vesktop_minecraft_*` | Unrelated Minecraft provider, kept here so the whole stack is versioned together. |
| `systemd/user/` | User units. `roaring-presenced.socket` activates the manager on demand. |
| `udev/` | Rule that starts the provider when a disc with audio tracks is inserted. |

## Install

```bash
./install.sh
# optional, needs root: start automatically on disc insert
sudo install -m 644 udev/99-roaring-presence-cd.rules /etc/udev/rules.d/
sudo udevadm control --reload
```

## Configuration

`~/.config/roaring-presence/config.json` (see `config/config.sample.json`).
Keys under `cd`:

| Key | Default | Meaning |
| --- | --- | --- |
| `device` | `"auto"` | Drive to watch, or auto-detect the one holding an audio disc. USB drives re-enumerate (`/dev/sr1` → `/dev/sr2`), so `auto` is recommended. |
| `poll_seconds` | `3` | Playback poll interval while something is playing. |
| `idle_poll_seconds` | `6` | Slower poll when nothing is playing. |
| `kernel_toc_first` | `true` | Read the TOC via ioctl instead of waiting on `cd-info`. |
| `cdtext_probe_timeout` | `12` | Cap on the CD-Text probe; a busy drive no longer stalls startup. |
| `metadata_grace_seconds` | `2.0` | How long the first publish waits for online metadata before going out without it. |
| `use_cover_art_archive` | `true` | Fetch cover art from the Cover Art Archive. |
| `show_progress_bar` | `true` | Publish `timestamps` so Discord draws the bar. |
| `progress_drift_seconds` | `2.5` | Only re-publish the bar when it actually drifted (seek, pause, stall). |
| `autoplay_prompt` | `true` | Offer to start playback on insert. Set `false` to disable. |
| `mpv_ipc_socket` | `$XDG_RUNTIME_DIR/mpv-ipc.sock` | Where mpv exposes position. |
| `links` | see below | Templates for the clickable song/album links. |

### Clickable links

Discord renders `details_url` on the song line and `state_url` on the album
line. Templates support `%(query)s`, `%(album_query)s` (URL-encoded
artist + title / artist + album), `%(release_id)s`, and `%(discid)s`:

```json
"links": {
  "track": "https://music.youtube.com/search?q=%(query)s",
  "album": "https://musicbrainz.org/release/%(release_id)s",
  "album_fallback": "https://music.youtube.com/search?q=%(album_query)s"
}
```

Swap in Spotify (`https://open.spotify.com/search/%(query)s`), Songwhip, or
anything else. `album_fallback` is used when MusicBrainz has no release for
the disc.

## Playing a disc

```bash
roaring-cd-autoplay --device /dev/sr1 --album      # whole disc
roaring-cd-autoplay --device /dev/sr1 --track 4    # one track
```

Playback is `mpv --cdda-device=DEV cdda://`, i.e. the raw disc. Tracks are
chapters of that stream, selected with `--start=#N` — mpv has no `cdda://N`
track syntax, and `--cdrom-device` was renamed to `--cdda-device` in mpv 0.40.

Reading `cdda://` directly is deliberate: opening the disc through KIO/kio-fuse
makes a worker transcode WAV while the provider reads the TOC, which fights
over the drive and makes the reported position drift. mpv also gets its own
transient systemd scope, so restarting the presence service never kills music.

## Metadata

1. Disc ID (MusicBrainz) — exact match when the disc is known.
2. If the disc ID is unknown, a CD-Text search of MusicBrainz releases, ranked
   by how closely the track count matches the disc.
3. Cover art from the Cover Art Archive: release first, then release-group.
4. Results cached in `~/.cache/roaring-presence/disc-<discid>.v2.json`.

All of it runs on a background thread, so presence appears from the kernel TOC
immediately and upgrades itself (titles, cover art) when the lookup lands. If a
lookup times out mid-way, whatever was already resolved is kept instead of
throwing the whole thing away.

Titles come from CD-Text, then MusicBrainz, then the filename, then
`Track N` — so a disc with no metadata at all still shows something sane.

## Eject

On eject (or tray open, or the drive vanishing) the provider clears the Discord
status within about a second and stops the playback it started. The autoplay
helper also runs its own watchdog, so playback stops even when the provider
isn't running. `SIGTERM` (`systemctl --user stop`, logout) clears the status
too, rather than leaving a stale "listening to" behind.

## Troubleshooting

```bash
journalctl --user -u 'roaring-cd-presence@*' -f      # provider
journalctl --user -u roaring-presenced -f            # manager + published payloads
tail -f ~/.cache/roaring-presence/autoplay.log       # what mpv said
roaring-cd-presence /dev/sr1 --once --dry-run -v     # print a payload, touch nothing
```

- **Nothing in Discord**: check the manager is connected — the socket path is
  probed from `ipc_socket_candidates` (Vesktop's flatpak path first).
- **No cover art**: some releases simply have none in the Cover Art Archive;
  `cover art lookup skipped: 404` is that, not a bug.
- **No per-track titles**: the disc had no CD-Text and the MusicBrainz detail
  fetch timed out. Album, artist, and cover still work; re-insert to retry.
- **Manager exits on its own**: by design, after `idle_exit_seconds` with no
  providers connected. The socket re-activates it.
