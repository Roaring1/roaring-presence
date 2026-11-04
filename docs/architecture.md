# Architecture and lifecycle

## Responsibility boundaries

```text
                  optical media event          launcher event
                         |                         |
                         v                         v
              per-disc audio-CD session      Minecraft provider
                         |                         |
                         v                    PID discovery once
               owned CD player process              |
               /       |       \\            pidfd + inotify
            window    mpv     MPRIS
                         |       |
                    desktop audio  KDE media controls
                         |
              optional provider socket
                         |
                         v
                core / roaring-presenced
                         |
                  one Discord IPC link
                         |
                         v
                  Discord client

         tools/assets: independent local image preparation
```

## Processing model

### Core

The core is an arbitrator, not a source collector. It accepts local provider
messages, chooses the highest-priority live activity, and is the only component
that talks to Discord. Its systemd socket is passive activation plumbing; the
manager exits when the final provider disconnects.

### Audio-CD

An insertion event starts one per-drive user service. The session reads the
kernel TOC and CD-Text, resolves optional online metadata, and starts one
owned player process. The player owns the window, its mpv child, the MPRIS2
registration, and drive-eject detection. Each optical drive gets a private mpv
IPC socket; the MPRIS service remains a single desktop player. There are no
detached playback watchdogs, transient systemd scopes, paused preloads, or
process-table scans for unrelated desktop players.

The player-only mode does not connect to the Discord core. The Discord-enabled
mode sends provider messages to the shared core. In that mode, the provider
requires an affirmative mpv state (`path` present and `pause` false) before it
publishes a song. Pause, stop, unknown state, player exit, and eject clear the
activity. Resume republishes it.

Closing the player stops and reaps mpv, releases MPRIS, and ends the per-disc
service. Eject follows the same cleanup path. KDE's taskbar and media controls
use the in-process MPRIS interface; the application installs no global
keyboard listener or separate media-key service.

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
clients, while component directories and installer profiles keep each feature
independently understandable and installable.

The root-level old paths are symlinks for compatibility. Canonical source and
packaging live beside each component. Deprecated direct-RPC bridge files are
kept in `legacy/` but are not part of the default install.

## Extension checklist

A provider should own its source-specific lifecycle, avoid broad polling after
source detection, publish only meaningful live state, clear on shutdown, close
its socket, and keep third-party network work outside the core. Add isolated
tests for its activity builder and lifecycle. Do not add another Discord IPC
connection or a generic resident watcher.
