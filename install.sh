#!/usr/bin/env bash
# Install roaring-presence for the current user.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

install -d "$HOME/bin" "$HOME/.config/systemd/user" "$HOME/.config/roaring-presence" \
  "$HOME/.local/share/applications"
install -m 755 "$HERE"/bin/* "$HOME/bin/"
install -m 644 "$HERE"/systemd/user/* "$HOME/.config/systemd/user/"
# Desktop entry: gives the MPRIS service a name and icon in the KDE panel.
install -m 644 "$HERE"/desktop/* "$HOME/.local/share/applications/"
command -v update-desktop-database >/dev/null &&
  update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

if [ ! -f "$HOME/.config/roaring-presence/config.json" ]; then
  install -m 644 "$HERE/config/config.sample.json" \
    "$HOME/.config/roaring-presence/config.json"
  echo "installed default config; set assets/client_id as needed"
fi

# "systemctl --user" needs the session bus.  Over ssh or from a non-graphical
# shell those variables are usually unset, and daemon-reload then fails with
# "Failed to connect to bus" -- which looks like a broken install but is not.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS=\
  "${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"
if ! systemctl --user daemon-reload 2>/dev/null; then
  echo "warning: no user systemd session reachable; run this from your desktop" >&2
  echo "         session, then: systemctl --user daemon-reload" >&2
else
  systemctl --user enable --now roaring-presenced.socket
fi

echo
echo "Optional (needs root) -- auto-start on disc insert:"
echo "  sudo install -m 644 $HERE/udev/99-roaring-presence-cd.rules /etc/udev/rules.d/"
echo "  sudo udevadm control --reload"
