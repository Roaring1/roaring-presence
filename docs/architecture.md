# Architecture and lifecycle

## Responsibility boundaries

```text
                   optical media event             launcher event
                          |                              |
                          v                              v
                   audio-CD session                Minecraft provider
                   /              \
          player-only mode      Discord mode                 |
             |                  |                            |
        kernel TOC          kernel TOC                 PID discovery once
        + playback          + playback                       |
        + MPRIS             + MPRIS                    pidfd + inotify
             |                  |
             |             local provider socket
             |                  |
             |                  v
             |          core / roaring-presenced
             |                  |
             |           one Discord IPC link
             |                  |
             v                  v
        Desktop audio       Discord client

        tools/assets: independent local image preparation commands
```

## Processing model

### Core

The core is an arbitrator, not a source collector. It accepts local provider
messages, chooses the highest-priority live activity, and is the only component
that talks to Discord. The systemd socket is passive activation plumbing. The
manager is short-lived when no provider is connected.

### Audio-CD

An insertion event starts one per-drive process. It performs immediate local
disc reads, then one bounded online metadata task (optional). It follows
playback and drive state for the lifetime of the inserted disc and checks for
ejects during that session. There are two modes over the same engine:

- **Player-only:** starts playback, publishes MPRIS/media-key controls, and
  monitors eject. It has no connection or dependency on the Discord core.
- **Discord-enabled:** does the same work, plus sends activity messages over
  the provider socket to the shared core. The core remains the only Discord
  IPC client.

Neither mode leaves a global drive-polling watcher running.

### Minecraft

The launcher starts the provider. A bounded startup probe identifies the game
process, after which Linux pidfd notification tracks the process lifetime and
inotify tracks changes to the instance log. The process table is not rescanned
during normal play. A targeted `--pid` entry point is available for launchers
that expose the actual game PID. Older-kernel fallback checks only that PID's
identity.

### Asset processing

Asset tooling is a finite, offline conversion job. It accepts arbitrary local
images, emits normalized square PNGs and a manifest, and never needs access to
a Discord account. The generated files are uploaded manually in the Developer
Portal.

## Why this is a monorepo

The providers share one local wire protocol, config location, and Discord
publisher. Keeping them together avoids multiple competing Discord IPC
clients, while the component directories and installer profiles make each
project independently understandable and installable.

The root-level old paths are symlinks for compatibility. Canonical source and
packaging live beside each component. Deprecated direct-RPC bridge files are
kept in `legacy/` but are not part of the default install.

## Extension checklist

A provider should own its source-specific lifecycle, avoid broad polling after
source detection, publish on meaningful changes, clear on shutdown, close its
socket, and keep third-party network work outside the core. Add an isolated
test for its activity builder and lifecycle. Do not make another Discord IPC
connection.
