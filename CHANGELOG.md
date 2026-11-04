# Changelog

Notable user-facing changes are recorded here.

## Unreleased

No unreleased changes.

## v0.1.0 — 2026-11-04

- Initial public release of the modular Linux audio-CD player with optional
  Discord Rich Presence, Minecraft activity, and local artwork tools.
- Split audio-CD playback from Discord publishing. The standalone
  `cd-player` profile needs no Discord client, IPC socket, core service, or
  Application ID; the optional `audio-cd` profile adds presence to the same
  single-owner player session.
- Simplified CD lifecycle ownership: one per-disc session owns the player,
  mpv child, MPRIS registration, and eject handling. Discord activity appears
  only during confirmed unpaused CD playback and clears on pause, stop, close,
  eject, and teardown.
- Added per-drive mpv IPC sockets, safe migration of legacy configuration and
  installed helper files, and a branch-pinned updater that tests fast-forward
  updates before installing the selected component profile.
- Added component-scoped diagnostics, distro installation guidance,
  compatibility notes, support/security instructions, and MIT licensing.
- CI passes on Python 3.10, 3.12, and 3.14. The offline suite contains 54
  regression tests.
- Real-drive validation on Nobara/KDE used an HL-DT-ST DVDRAM GP60NB50 with
  two audio CDs (11 and 17 tracks), and Vesktop Flatpak for Discord IPC.
  Playback, pause/resume presence clearing/restoration, track changes, session
  close, physical eject, and eject/reinsert were verified.

### Known limitations

- KDE Plasma's taskbar has been observed to grey out its Next/Previous controls
  even while the player UI works and KDE's MPRIS model reads the advertised
  capabilities as available. Direct MPRIS calls work; the taskbar-specific
  mismatch was not reproduced in the isolated headless test and has no
  confirmed root cause.
- Only Vesktop Flatpak has been exercised end-to-end for Discord publishing
  on the maintainer's desktop. Native Discord, official Discord Flatpak,
  Snap, other desktops, and non-Fedora distributions are not all hardware-
  validated.
- The hardware run exercised the Discord-enabled player profile. The
  standalone profile is covered by CI installer/smoke tests but has not had a
  separate physical-drive acceptance run.
