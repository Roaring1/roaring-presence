# Security policy

## Scope

The project runs as the current Linux user. Its provider and manager socket is
created in the user's runtime directory and should remain private to that user
(mode `0600`). The project does not need Discord bot credentials; the Discord
Application ID is public configuration.

Do not publish real configuration files, runtime socket contents, private
filesystem paths, or logs that contain personal information in bug reports.

## Reporting a vulnerability

Please use GitHub's **Report a vulnerability** action for this repository when
private vulnerability reporting is available. Do not file an issue containing
an unpatched vulnerability or exploit details. Include the affected commit,
component, Linux distribution/release, and a minimal reproduction that excludes
credentials and personal data.

## Supported security expectations

- No automatic root escalation or system-wide permission changes.
- No automatic Flatpak or Snap permission modifications.
- No network listener; provider sockets are local Unix sockets.
- Network access is limited to configured metadata/artwork lookups and the
  Discord client's local RPC endpoint.
- User configuration is preserved by the installer and updater.
