#!/usr/bin/env bash
# Install selected roaring-presence components for the current user.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

declare -A SELECTED=()
COMPONENT_SET=0
ENABLE_LOGIN_SCAN=0
REMOVE_LEGACY_BRIDGE=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Components (repeat --component to combine them):
  core        Discord Rich Presence manager and read-only doctor
  audio-cd    Optical-disc provider, player, autoplay and udev integration
  minecraft   Launcher-triggered Minecraft provider
  assets      Generic image packer and built-in artwork generator
  all         All components (default)

Options:
  --component NAME       Install one component (may be repeated).
  --enable-login-scan    Run one short audio-CD catch-up scan at desktop login.
  --remove-legacy-bridge Stop/remove the obsolete standalone socat bridge.
  -h, --help             Show this help.

Examples:
  ./install.sh
  ./install.sh --component audio-cd
  ./install.sh --component minecraft --component assets

Provider selections include the small core manager automatically. The manager
is socket-activated and exits shortly after its final provider disconnects.
Providers are started by optical-drive or launcher events, not enabled as
permanent login services.
EOF
}

while (($#)); do
  case "$1" in
    --component)
      [[ $# -ge 2 ]] || { echo "--component needs a name" >&2; exit 2; }
      COMPONENT_SET=1
      case "$2" in
        core|audio-cd|minecraft|assets|all) SELECTED["$2"]=1 ;;
        *) echo "unknown component: $2" >&2; usage >&2; exit 2 ;;
      esac
      shift 2
      ;;
    --enable-login-scan) ENABLE_LOGIN_SCAN=1; shift ;;
    --remove-legacy-bridge) REMOVE_LEGACY_BRIDGE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -n "${SELECTED[all]:-}" ]]; then
  SELECTED=( [core]=1 [audio-cd]=1 [minecraft]=1 [assets]=1 )
elif [[ "$COMPONENT_SET" -eq 0 ]]; then
  if [[ "$REMOVE_LEGACY_BRIDGE" -eq 1 && "$ENABLE_LOGIN_SCAN" -eq 0 ]]; then
    : # Explicit cleanup-only invocation; install no components.
  elif [[ "$ENABLE_LOGIN_SCAN" -eq 1 ]]; then
    SELECTED=( [core]=1 [audio-cd]=1 )
  else
    SELECTED=( [core]=1 [audio-cd]=1 [minecraft]=1 [assets]=1 )
  fi
fi
# Providers talk to the core socket. Assets are deliberately standalone.
if [[ -n "${SELECTED[audio-cd]:-}" || -n "${SELECTED[minecraft]:-}" || "$ENABLE_LOGIN_SCAN" -eq 1 ]]; then
  SELECTED[core]=1
fi
if [[ "$ENABLE_LOGIN_SCAN" -eq 1 ]]; then
  SELECTED[audio-cd]=1
fi

install -d "$HOME/bin"
if [[ -n "${SELECTED[core]:-}" || -n "${SELECTED[audio-cd]:-}" || -n "${SELECTED[minecraft]:-}" ]]; then
  install -d "$HOME/.config/roaring-presence"
fi

if [[ -n "${SELECTED[core]:-}" ]]; then
  install -m 755 "$HERE/core/bin/roaring-presenced" "$HOME/bin/roaring-presenced"
  install -m 755 "$HERE/core/bin/roaring-presence-doctor" "$HOME/bin/roaring-presence-doctor"
  install -d "$HOME/.config/systemd/user"
  install -m 644 "$HERE/core/systemd/user/roaring-presenced.service" "$HOME/.config/systemd/user/"
  install -m 644 "$HERE/core/systemd/user/roaring-presenced.socket" "$HOME/.config/systemd/user/"
fi

if [[ -n "${SELECTED[audio-cd]:-}" ]]; then
  install -m 755 "$HERE/providers/audio-cd/bin/roaring-cd-presence" "$HOME/bin/"
  install -m 755 "$HERE/providers/audio-cd/bin/roaring-cd-autoplay" "$HOME/bin/"
  install -m 755 "$HERE/providers/audio-cd/bin/roaring-cd-player" "$HOME/bin/"
  install -m 755 "$HERE/providers/audio-cd/bin/roaring-presence-scan" "$HOME/bin/"
  install -d "$HOME/.config/systemd/user" "$HOME/.local/share/applications"
  install -m 644 "$HERE/providers/audio-cd/systemd/user/roaring-cd-presence-scan.service" "$HOME/.config/systemd/user/"
  install -m 644 "$HERE/providers/audio-cd/systemd/user/roaring-cd-presence@.service" "$HOME/.config/systemd/user/"
  install -m 644 "$HERE/providers/audio-cd/desktop/roaring-cd-player.desktop" "$HOME/.local/share/applications/"
  command -v update-desktop-database >/dev/null &&
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

if [[ -n "${SELECTED[minecraft]:-}" ]]; then
  install -m 755 "$HERE/providers/minecraft/bin/roaring-minecraft-presence" "$HOME/bin/"
  install -d "$HOME/.config/systemd/user"
  install -m 644 "$HERE/providers/minecraft/systemd/user/roaring-minecraft-presence.service" "$HOME/.config/systemd/user/"
fi

if [[ -n "${SELECTED[assets]:-}" ]]; then
  install -m 755 "$HERE/tools/assets/bin/roaring-presence-assets" "$HOME/bin/"
  install -m 755 "$HERE/tools/assets/bin/roaring-presence-art.py" "$HOME/bin/"
fi

if [[ -n "${SELECTED[core]:-}" || -n "${SELECTED[audio-cd]:-}" || -n "${SELECTED[minecraft]:-}" ]]; then
  if [[ ! -f "$HOME/.config/roaring-presence/config.json" ]]; then
    install -m 644 "$HERE/config/config.sample.json" "$HOME/.config/roaring-presence/config.json"
    echo "installed default config; set client_id to your Discord Application ID"
  fi
fi

# The old bridge only served the superseded standalone Minecraft RPC program.
# Removing it is explicit so installation never interrupts a user's session.
if [[ -n "${SELECTED[core]:-}" || -n "${SELECTED[audio-cd]:-}" || -n "${SELECTED[minecraft]:-}" || "$REMOVE_LEGACY_BRIDGE" -eq 1 ]]; then
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"
  if ! systemctl --user daemon-reload 2>/dev/null; then
    echo "warning: no user systemd session reachable; run this from your desktop session" >&2
    echo "         session, then: systemctl --user daemon-reload" >&2
  else
    if [[ -n "${SELECTED[core]:-}" ]]; then
      systemctl --user enable --now roaring-presenced.socket
    fi
    if [[ "$ENABLE_LOGIN_SCAN" -eq 1 ]]; then
      systemctl --user enable roaring-cd-presence-scan.service
    fi
    if [[ "$REMOVE_LEGACY_BRIDGE" -eq 1 ]]; then
      systemctl --user disable --now discord-rpc-bridge.service 2>/dev/null || true
      rm -f "$HOME/.config/systemd/user/discord-rpc-bridge.service"
      systemctl --user daemon-reload
      echo "removed legacy discord-rpc-bridge.service"
    elif systemctl --user is-enabled --quiet discord-rpc-bridge.service 2>/dev/null; then
      echo "note: the obsolete discord-rpc-bridge.service is still enabled."
      echo "      Remove with: ./install.sh --remove-legacy-bridge"
    fi
  fi
fi

echo
echo "Installed components:"
for component in core audio-cd minecraft assets; do
  if [[ -n "${SELECTED[$component]:-}" ]]; then echo "  - $component"; fi
done
if [[ -n "${SELECTED[audio-cd]:-}" ]]; then
  echo
  echo "Optional: automatic audio-CD insert activation (requires root once):"
  echo "  sudo install -m 644 $HERE/providers/audio-cd/udev/99-roaring-presence-cd.rules /etc/udev/rules.d/"
  echo "  sudo udevadm control --reload"
  echo "Optional: one-shot CD catch-up scan at each login:"
  echo "  ./install.sh --enable-login-scan"
fi
if [[ -n "${SELECTED[core]:-}" || -n "${SELECTED[audio-cd]:-}" || -n "${SELECTED[minecraft]:-}" ]]; then
  echo
  echo "Run: roaring-presence-doctor"
elif [[ -n "${SELECTED[assets]:-}" ]]; then
  echo
  echo "Try the asset tools:"
  echo "  roaring-presence-assets --help"
  echo "  roaring-presence-art.py --help"
elif [[ "$REMOVE_LEGACY_BRIDGE" -eq 1 ]]; then
  echo
  echo "Legacy bridge cleanup-only mode; no components were installed."
fi
