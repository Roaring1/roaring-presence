# Support

`roaring-presence` is a Linux-first desktop project. Please read the relevant
guide before opening an issue:

- [Linux installation and dependencies](docs/linux-installation.md)
- [Audio-CD player](providers/audio-cd/README.md)
- [Discord client compatibility](docs/discord-client-compatibility.md)
- [Architecture and provider protocol](docs/architecture.md)
- [Hardware validation notes](docs/hardware-validation.md)

## Current support scope

The maintained target is Linux with a systemd user session, Unix sockets, and
Linux optical-drive support for CD playback. The standalone CD player does
not require Discord. Discord Rich Presence requires a running compatible
desktop client that exposes local RPC-over-IPC.

Vesktop Flatpak has been exercised end-to-end on one Nobara/KDE desktop.
Other native, Flatpak, and Snap packaging combinations are documented where
known, but should not be treated as hardware-verified until listed as tested
in the [client compatibility guide](docs/discord-client-compatibility.md).

Windows, macOS, browser-only Discord, mobile clients, and non-systemd Linux
setups are not currently supported targets.

## Before reporting a problem

1. Update to the latest commit on your installed branch.
2. Run the relevant read-only doctor command:

   ```bash
   ~/.local/bin/roaring-presence-doctor --component cd-player
   ~/.local/bin/roaring-presence-doctor --component audio-cd
   ```

3. Include the component, install profile, distribution/release, desktop,
   optical drive model (for CD issues), and relevant software versions.
4. Include the doctor output and a short, sanitized journal excerpt. Remove
   usernames, private filesystem paths, Discord identifiers, and unrelated
   personal information before posting.

Do not post passwords, bot tokens, private configuration files, runtime socket
data, or unredacted personal logs. The Discord Application ID is public, but
there is no need to include it in a bug report.

Bug reports and feature requests can be opened through the repository's
[issue tracker](https://github.com/Roaring1/roaring-presence/issues).
