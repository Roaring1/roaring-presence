# Hardware validation

## Audio-CD to Discord Rich Presence — 2026-10-30

A real optical-drive integration test was completed on the desktop after the
modular deployment.

**Hardware and runtime**

- Linux desktop, KDE Plasma 6.6.4, PipeWire 1.4.11, Vesktop/Discord IPC.
- Optical drive: HL-DT-ST DVDRAM GP60NB50 (`/dev/sr0`).
- Audio CD: *Alabama & Friends*, 11 audio tracks.
- Core socket activation and the audio-CD provider from
  `event-driven-audit-refresh`.

**Initial live result**

1. Inserting the disc started `roaring-cd-presence@sr0.service`.
2. The provider read the kernel table of contents and detected all 11 tracks.
3. The autoplay/player UI opened immediately.
4. The provider connected to the local `roaring-presenced` socket.
5. Discord displayed the CD activity with artist/album/track information and
   playback timing, alongside the existing Essential Mod / Minecraft status.
6. The activity advanced from track 1 to track 2 in the provider and manager
   logs. MusicBrainz metadata supplied track names although the disc had no
   CD-Text.

**Artwork issue diagnosed and corrected in source**

The first live lookup resolved MusicBrainz release
`d668a3bf-4040-4123-aeab-e923e8c7d560`, but Cover Art Archive had no image at
the release level. The MusicBrainz DiscID response included recordings but
omitted the release-group ID because the request did not ask for
`release-groups`; the old resolver also skipped the detail lookup when tracks
were already present. The artwork existed only at release-group level.

The fixed resolver requests release-group metadata, checks both release and
release-group artwork, and upgrades old negative cache entries once. Running
the new resolver against the still-inserted disc found this front-cover
thumbnail and wrote it to the existing disc cache:

`https://coverartarchive.org/release/3584a2b2-fdb2-454d-a927-e315a3b2cc08/5821050208-500.jpg`

The activity builder already prefers the resolved HTTPS cover URL over the
generic configured `cd` asset. A fresh provider publish is needed to refresh
the current Discord card from the pre-fix in-memory metadata.

**KDE per-app volume integration diagnosed and corrected in source**

The player already registers MPRIS as `org.mpris.MediaPlayer2.roaringcd`,
reports Identity `Audio CD`, and uses the matching `roaring-cd-player.desktop`
entry. Plasma's task-manager tooltip volume controls are enabled by default.
The original mpv native PipeWire stream identified itself only as `mpv`, so
Plasma could not associate it with the visible Audio CD task.

The new autoplay command selects mpv's PulseAudio compatibility output and
sets `--audio-client-name=Audio CD`. A silent, zero-volume test stream
confirmed PipeWire then publishes `application.name=Audio CD`, the fallback
identity Plasma's task manager uses to associate an application audio stream
with its task. The current already-running mpv process keeps its old identity
until the player is relaunched with the new options.

**Relevant runtime observations**

- Provider startup and TOC detection: 19:05:27 PDT.
- Manager connection: 19:05:36 PDT.
- Track 1 published: 19:05:39 PDT.
- Track 2 published: 19:05:55 PDT.
- The release-level CAA endpoint returned HTTP 404; the release-group endpoint
  returned one front image.

**Scope and remaining checks**

This validates the real insert-to-player-to-manager-to-Discord path. The fixed
metadata resolver was exercised against the real inserted disc, but the
current provider process still had the pre-fix in-memory metadata at the time
of this note. The KDE audio identity was verified with a harmless silent test
stream; the live CD stream needs a new mpv process before the taskbar slider
can be verified visually. Eject cleanup and other drive/media combinations
remain separate tests.

The legacy Vesktop-to-Prism IPC bridge was left enabled during validation. It
preserves the pre-existing Minecraft/Essential Mod integration and was not
disabled.
