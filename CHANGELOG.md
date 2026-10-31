# Changelog

Notable user-facing changes are recorded here. This project has not published a
versioned release yet; unreleased work remains under **Unreleased** until a tag
is created.

## Unreleased

- Split audio-CD playback from Discord Rich Presence. The standalone `cd-player`
  profile has no Discord core, client, IPC or Application ID dependency.
- Added a Discord-enabled CD profile that reuses the standalone CD session
  engine, plus separate user services and opt-in udev activation.
- Standardized installation on XDG directories and `~/.local/bin`, with
  absolute desktop/service executable paths and compatibility symlinks for
  existing `~/bin` commands.
- Added a GitHub-branch updater that checks for clean/fast-forward state,
  verifies new code in an isolated worktree, tests it, and refreshes only the
  selected components.
- Improved component-aware diagnostics, audio-backend fallback, optional Qt
  UI handling, generic Discord IPC discovery, and distro installation docs.
- Expanded the offline regression and installer test suite and CI matrix to
  Python 3.10, 3.12 and 3.14.
- Adopted the MIT License for original project code and documentation.
