# roaring-presence

Discord Rich Presence for actual audio CDs, on Linux.

Put a disc in the drive and Discord shows what's spinning: artist, track,
album, cover art, real progress bar. A window pops up with the track list so
you can actually run the thing. Take the disc out and it all goes away.

Nothing phones home and nothing asks Spotify what you're listening to. The
disc is the source of truth. The TOC and CD-Text come straight off the drive
via ioctl, and the position comes from mpv over its IPC socket. There's no
background daemon sitting around either -- udev starts it on insert, it exits
when the disc is gone.

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
| `kernel_cdtext` | `true` | Read CD-Text via `SG_IO` / `READ TOC` format 5 instead of shelling out to `cd-info`. Set `false` to force the `cd-info` path. |
| `cdtext_probe_timeout` | `12` | Cap on the `cd-info` CD-Text probe. Only used when `kernel_cdtext` is off or came back empty. |
| `cd_info_timeout` | `45` | Same: `cd-info` fallback only. |
| `cd_info_attempts` | `2` | Same: `cd-info` fallback only. |
| `metadata_grace_seconds` | `2.0` | How long the first publish waits for online metadata before going out without it. |
| `use_cover_art_archive` | `true` | Fetch cover art from the Cover Art Archive. |
| `show_progress_bar` | `true` | Publish `timestamps` so Discord draws the bar. |
| `progress_drift_seconds` | `2.5` | Only re-publish the bar when it actually drifted (seek, pause, stall). |
| `autoplay_prompt` | `true` | Offer to start playback on insert. Set `false` to disable. |
| `preload` | `true` | Open the disc paused right after insert so the first play is instant. See [Preload](#preload). |
| `preload_idle_seconds` | `60` | If you never touch the window, the preload is dropped after this long and the drive spins down. |
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

## Controls

Inserting a disc opens `roaring-cd-player`: a small window with the cover, the
track list, and prev / play-pause / next.  It is both the insert prompt and the
transport -- pick “Entire album” or any track, and the same window keeps
controlling playback instead of disappearing.

It also publishes **MPRIS2** as `org.mpris.MediaPlayer2.roaringcd`, which is
what makes the **keyboard media keys** work, along with the KDE panel widget,
the lock screen, and `playerctl`.  mpv has no MPRIS of its own unless the
mpv-mpris plugin is installed, so the player provides it and proxies every
call to mpv over the IPC socket.

### Track names

Plenty of discs ship CD-Text that just says `Track 1`, `Track 2`, ... which is
useless. When the disc names look like placeholders and MusicBrainz has real
ones, the real names win. If both sides have something real and they disagree,
you get the disc's name with the other one after it in grey parentheses:

```
 3.  Intro (Entrance Hall)
```

The grey half is capped at half the row and elided, so a long alternate name
can't push the actual title off the edge. Hover for the full thing.

### Buttons and keys

Double-click a track (or select it and press Enter) to play it; `Space`,
`Left` and `Right` work as play/pause and skip.  Every press is acknowledged
immediately: the button sinks for a moment to show the click was consumed,
stays dimmed while the command is still unconfirmed, and shows a count when
several presses are outstanding.  Rapid skips are coalesced into a single
seek, so spamming skip lands on the track you would expect rather than
queueing up a backlog.  While a cold drive is spinning up, the play button
becomes a spinner and the progress bar goes indeterminate.

All mpv IPC and every drive ioctl run on a worker thread, and mpv state
arrives through `observe_property` rather than polling, so the window never
blocks on the drive or the socket.

Closing the window does not quit while a disc is playing: the MPRIS service
stays up so the media keys keep working.  Reopen it from the panel, from the
“Audio CD” launcher entry, or with `roaring-cd-player --device /dev/sr1`.
The process exits on eject.

Track skipping is chapter navigation, because `cdda://` is one stream whose
chapters are the tracks.  Previous behaves like a CD deck: it restarts the
current track unless you are within the first 3 seconds.

Media keys go to whichever player the desktop considers active, so if another
app grabs them, raise this window (or pause the other player) to hand them
back.

| Key | Meaning |
| --- | --- |
| `player_ui` | Open the control window on insert. `false` falls back to the old kdialog menu. |
| `player_poll_seconds` | Poll interval while playing. |
| `player_idle_poll_seconds` | Poll interval while stopped. |

## Preload

The annoying bit about the old flow: insert a disc, wait for it to be read,
the drive spins down while you decide, then you hit play and wait for it to
spin up *again*. Two waits for one album.

So the drive is already awake when the window opens, and the window quietly
opens the disc paused at track 1 (`roaring-cd-autoplay --preload`, which is
mpv with `--pause=yes --idle=yes --cache=yes`). Hitting play just unpauses --
no second spin-up.

It isn't a guess about what you want, and it doesn't count as playback:

- no spinner and no indeterminate bar, since you didn't ask for anything yet
- Discord isn't told anything; a paused preload isn't "listening to"
- touch any control -- play, pause, skip, a track, "Entire album" -- and the
  warm mpv just becomes your session
- touch nothing for `preload_idle_seconds` (60 by default) and it quits mpv
  again, so the drive spins down like before

Set `"preload": false` under `cd` if you'd rather the drive stay quiet.

## Playing a disc

The window is the easy path; these are for scripts and keybindings:

```bash
roaring-cd-autoplay --device /dev/sr1 --album      # whole disc
roaring-cd-autoplay --device /dev/sr1 --track 4    # one track
roaring-cd-autoplay --device /dev/sr1 --preload    # open it paused, don't play
roaring-cd-player   --device /dev/sr1              # (re)open the controls
roaring-cd-player   --device /dev/sr1 --no-window  # media keys only, no UI
```

Playback is `mpv --cdda-device=DEV cdda://`, i.e. the raw disc. Tracks are
chapters of that stream, selected with `--start=#N` — mpv has no `cdda://N`
track syntax, and `--cdrom-device` was renamed to `--cdda-device` in mpv 0.40.

Reading `cdda://` directly is deliberate: opening the disc through KIO/kio-fuse
makes a worker transcode WAV while the provider reads the TOC, which fights
over the drive and makes the reported position drift. mpv also gets its own
transient systemd scope, so restarting the presence service never kills music.

## Metadata

### Reading the disc

The TOC and CD-Text both come straight from the kernel: an `SG_IO` passthrough
of `READ TOC/PMA/ATIP` (opcode `0x43`), format 5 for CD-Text. This reads album,
artist, and per-track titles in well under a second.

`cd-info` is now only a fallback for when `kernel_cdtext` is disabled or the
drive returns no CD-Text block. That matters because some drives never answer
`cd-info` at all -- it would sit there until `cd_info_timeout` expired and hand
back nothing, leaving album and artist as `?`. On those drives the kernel reader
is the difference between full metadata and none.

### Looking it up

1. Disc ID (MusicBrainz) — exact match when the disc is known.
2. If the disc ID is unknown, a CD-Text search of MusicBrainz releases, ranked
   by how closely the track count matches the disc.
3. Cover art from the Cover Art Archive: release first, then release-group.
4. Results cached in `~/.cache/roaring-presence/disc-<discid>.v2.json`.

All of it runs on a background thread, so presence appears from the kernel TOC
immediately and upgrades itself (titles, cover art) when the lookup lands. If a
lookup times out mid-way, whatever was already resolved is kept instead of
throwing the whole thing away.

MusicBrainz requests are serialised at most one per 1.1s (their published rate
limit) and retried up to three times on 5xx, 429, and transport errors with
geometric backoff. A `404` is a real answer -- an unknown disc ID -- and is never
retried. Without the throttle a burst of disc-id, search, detail, and cover-art
calls reliably drew back a wall of `503`s.

If the lookup still comes back empty, it is retried in the background 20s, 45s,
and 120s later, re-probing CD-Text as well whenever the drive is idle.

Titles come from CD-Text, then MusicBrainz, then the filename, then
`Track N`, so a disc with nothing at all still shows something. The one
exception is placeholder CD-Text: if the disc says `Track 4` and MusicBrainz
has a real name, the real name wins (see [Track names](#track-names)).

## Eject

Eject, open the tray, or yank the drive: the status clears in about a second
and whatever playback it started is stopped. The autoplay helper watches for
this itself, so music stops even if the provider isn't running. `SIGTERM`
(`systemctl --user stop`, logging out) clears it too, so you don't get left
with a stale "listening to".

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
  fetch timed out. Album, artist, and cover still work; the background retry
  has another go at 20s, 45s, and 120s.
- **Album and artist show as `?`**: neither the kernel CD-Text read nor the
  MusicBrainz disc ID found anything, which is expected for a disc that is
  pressed without CD-Text and not yet in MusicBrainz. Check the reader itself
  with `roaring-cd-presence /dev/sr1 --once --dry-run -v` and look for the
  `CD-Text:` line.
- **Repeated `503` from MusicBrainz**: you are being rate-limited. The client
  already paces itself; if you lowered `poll_seconds` a long way, raise it.
- **Manager exits on its own**: that's on purpose, after `idle_exit_seconds`
  with no providers connected. The socket starts it again when needed.
- **Drive spins up on its own after insert**: that's the preload. Set
  `"preload": false` under `cd` to turn it off.
- **Track names look wrong**: the grey name in parentheses is the other
  source's guess (usually MusicBrainz vs CD-Text). `roaring-cd-presence
  /dev/sr1 --once --dry-run -v` shows both.
