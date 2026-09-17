#!/usr/bin/env bash
# Install roaring-presence for the current user.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

install -d "$HOME/bin" "$HOME/.config/systemd/user" "$HOME/.config/roaring-presence"
install -m 755 "$HERE"/bin/* "$HOME/bin/"
install -m 644 "$HERE"/systemd/user/* "$HOME/.config/systemd/user/"

if [ ! -f "$HOME/.config/roaring-presence/config.json" ]; then
  install -m 644 "$HERE/config/config.sample.json" \
    "$HOME/.config/roaring-presence/config.json"
  echo "installed default config; set assets/client_id as needed"
fi

systemctl --user daemon-reload
systemctl --user enable --now roaring-presenced.socket

echo
echo "Optional (needs root) -- auto-start on disc insert:"
echo "  sudo install -m 644 $HERE/udev/99-roaring-presence-cd.rules /etc/udev/rules.d/"
echo "  sudo udevadm control --reload"
