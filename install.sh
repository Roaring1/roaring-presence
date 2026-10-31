#!/usr/bin/env bash
# Install selected roaring-presence components for the current user.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
CONFIG_ROOT="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_DIR="$CONFIG_ROOT/roaring-presence"

# Component names describe user-facing capabilities. `audio-cd` remains the
# compatibility name for the Discord publisher; `discord-cd` is its clearer
# alias. The standalone player is the safe default.
declare -A SELECTED=()
COMPONENT_SET=0
ENABLE_LOGIN_SCAN=0
REMOVE_LEGACY_BRIDGE=0

usage() {
  cat <<'USAGE'
Usage: ./install.sh [options]

Components (repeat --component to combine them):
  cd-player   Standalone Linux audio-CD player (default; no Discord required)
  audio-cd    CD playback + Discord Rich Presence (includes core automatically)
  discord-cd  Alias for audio-cd
  core        Discord Rich Presence manager and read-only doctor
  minecraft   Launcher-triggered Minecraft activity provider
  assets      Generic image packer and optional artwork generator
  all         All components

Options:
  --component NAME       Install one component (may be repeated).
  --enable-login-scan    Run one short CD catch-up scan at desktop login.
  --remove-legacy-bridge Stop/remove the obsolete standalone socat bridge.
  -h, --help             Show this help.

Examples:
  ./install.sh
  ./install.sh --component audio-cd
  ./install.sh --component cd-player --enable-login-scan
  ./install.sh --component minecraft --component assets

The installer is per-user. It writes commands to ~/.local/bin, preserves
existing configuration, and never runs sudo or changes system permissions.
Automatic optical-disc insertion is an optional, separate udev-rule step.
USAGE
}

while (($#)); do
  case "$1" in
    --component)
      [[ $# -ge 2 ]] || { echo "--component needs a name" >&2; exit 2; }
      COMPONENT_SET=1
      case "$2" in
        core|cd-player|minecraft|assets|all) SELECTED["$2"]=1 ;;
        audio-cd|discord-cd) SELECTED[audio-cd]=1 ;;
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
  SELECTED=([core]=1 [cd-player]=1 [audio-cd]=1 [minecraft]=1 [assets]=1)
elif [[ "$COMPONENT_SET" -eq 0 ]]; then
  if [[ "$REMOVE_LEGACY_BRIDGE" -eq 1 && "$ENABLE_LOGIN_SCAN" -eq 0 ]]; then
    : # Explicit cleanup-only invocation.
  else
    SELECTED[cd-player]=1
  fi
fi

# Rich Presence and Minecraft providers share the core. The player-only
# profile deliberately does not acquire that dependency.
if [[ -n "${SELECTED[audio-cd]:-}" || -n "${SELECTED[minecraft]:-}" ]]; then
  SELECTED[core]=1
fi
if [[ "$ENABLE_LOGIN_SCAN" -eq 1 ]]; then
  SELECTED[cd-player]=1
fi

HAS_CD=0
[[ -n "${SELECTED[cd-player]:-}" || -n "${SELECTED[audio-cd]:-}" ]] && HAS_CD=1
PLAYER_ONLY_CD=0
if [[ -n "${SELECTED[cd-player]:-}" && -z "${SELECTED[audio-cd]:-}" ]]; then
  PLAYER_ONLY_CD=1
fi

install_bin() {
  local name="$1" source="$2"
  install -m 755 "$source" "$BIN_DIR/$name"
  # Keep old ~/bin entry points working without leaving two independently
  # updated copies. Only replace paths whose names belong to this project.
  if [[ -d "$HOME/bin" ]]; then
    ln -sfn "$BIN_DIR/$name" "$HOME/bin/$name"
  fi
}

install -d "$BIN_DIR"
if [[ -n "${SELECTED[core]:-}" || -n "${SELECTED[audio-cd]:-}" || -n "${SELECTED[minecraft]:-}" ]]; then
  install -d "$CONFIG_DIR"
fi

if [[ -n "${SELECTED[core]:-}" ]]; then
  install_bin roaring-presenced "$HERE/core/bin/roaring-presenced"
  install_bin roaring-presence-doctor "$HERE/core/bin/roaring-presence-doctor"
  install -d "$CONFIG_ROOT/systemd/user"
  install -m 644 "$HERE/core/systemd/user/roaring-presenced.service" "$CONFIG_ROOT/systemd/user/"
  install -m 644 "$HERE/core/systemd/user/roaring-presenced.socket" "$CONFIG_ROOT/systemd/user/"
fi

if [[ "$HAS_CD" -eq 1 ]]; then
  install_bin roaring-presence-doctor "$HERE/core/bin/roaring-presence-doctor"
  install_bin roaring-cd-presence "$HERE/providers/audio-cd/bin/roaring-cd-presence"
  install_bin roaring-cd-session "$HERE/providers/audio-cd/bin/roaring-cd-session"
  install -m 644 "$HERE/providers/audio-cd/bin/cd_paths.py" "$BIN_DIR/cd_paths.py"
  install_bin roaring-cd-autoplay "$HERE/providers/audio-cd/bin/roaring-cd-autoplay"
  install_bin roaring-cd-player "$HERE/providers/audio-cd/bin/roaring-cd-player"
  install_bin roaring-presence-scan "$HERE/providers/audio-cd/bin/roaring-presence-scan"
  install -d "$CONFIG_ROOT/systemd/user" "$DATA_ROOT/applications"

  if [[ "$PLAYER_ONLY_CD" -eq 1 ]]; then
    install -m 644 "$HERE/providers/audio-cd/systemd/user/roaring-cd-player@.service" "$CONFIG_ROOT/systemd/user/"
    install -m 644 "$HERE/providers/audio-cd/systemd/user/roaring-cd-player-scan.service" "$CONFIG_ROOT/systemd/user/"
  else
    install -m 644 "$HERE/providers/audio-cd/systemd/user/roaring-cd-presence@.service" "$CONFIG_ROOT/systemd/user/"
    install -m 644 "$HERE/providers/audio-cd/systemd/user/roaring-cd-presence-scan.service" "$CONFIG_ROOT/systemd/user/"
  fi

  # Desktop Exec entries are generated with the absolute installed path; they
  # must not rely on a desktop shell inheriting ~/.local/bin in PATH.
  python3 - "$HERE/providers/audio-cd/desktop/roaring-cd-player.desktop" \
      "$DATA_ROOT/applications/roaring-cd-player.desktop" "$BIN_DIR" <<'PYDESKTOP'
from pathlib import Path
import sys
source, destination, bindir = map(Path, sys.argv[1:])
text = source.read_text(encoding="utf-8")
executable = str(bindir / "roaring-cd-player")
if any(char.isspace() for char in executable):
    executable = '"' + executable.replace("\\", "\\\\").replace('"', '\\"') + '"'
text = text.replace("@ROARING_PRESENCE_EXEC@", executable)
if "@ROARING_PRESENCE_EXEC@" in text:
    raise SystemExit("unexpanded desktop Exec placeholder")
destination.write_text(text, encoding="utf-8")
PYDESKTOP
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DATA_ROOT/applications" 2>/dev/null || true
  fi
fi

if [[ -n "${SELECTED[minecraft]:-}" ]]; then
  install_bin roaring-minecraft-presence "$HERE/providers/minecraft/bin/roaring-minecraft-presence"
  install -d "$CONFIG_ROOT/systemd/user"
  install -m 644 "$HERE/providers/minecraft/systemd/user/roaring-minecraft-presence.service" "$CONFIG_ROOT/systemd/user/"
fi

if [[ -n "${SELECTED[assets]:-}" ]]; then
  install_bin roaring-presence-assets "$HERE/tools/assets/bin/roaring-presence-assets"
  install_bin roaring-presence-art.py "$HERE/tools/assets/bin/roaring-presence-art.py"
fi

if [[ -n "${SELECTED[core]:-}" || -n "${SELECTED[audio-cd]:-}" || -n "${SELECTED[minecraft]:-}" ]]; then
  if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
    install -m 644 "$HERE/config/config.sample.json" "$CONFIG_DIR/config.json"
    echo "installed default config; set client_id to your Discord Application ID"
  fi
fi

# Persist the exact source checkout and component selection so a future update
# can fetch, test, and reinstall the same profile without guessing.
if git -C "$HERE" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  SOURCE_BRANCH="$(git -C "$HERE" branch --show-current 2>/dev/null || true)"
  SOURCE_REMOTE="$(git -C "$HERE" remote get-url origin 2>/dev/null || true)"
  if [[ -n "$SOURCE_BRANCH" && -n "$SOURCE_REMOTE" ]] && (( ${#SELECTED[@]} > 0 )); then
    PROFILE_ARGS=()
    if [[ "$COMPONENT_SET" -eq 0 ]]; then
      PROFILE_ARGS+=(--component cd-player)
    elif [[ -n "${SELECTED[all]:-}" ]]; then
      PROFILE_ARGS+=(--component all)
    else
      for component in core cd-player audio-cd minecraft assets; do
        [[ -n "${SELECTED[$component]:-}" ]] && PROFILE_ARGS+=(--component "$component")
      done
    fi
    [[ "$ENABLE_LOGIN_SCAN" -eq 1 ]] && PROFILE_ARGS+=(--enable-login-scan)
    printf -v SOURCE_DIR_Q '%q' "$HERE"
    printf -v SOURCE_BRANCH_Q '%q' "$SOURCE_BRANCH"
    printf -v SOURCE_REMOTE_Q '%q' "$SOURCE_REMOTE"
    printf -v PROFILE_ARGS_Q '%q ' "${PROFILE_ARGS[@]}"
    UPDATE_CORE=0
    UPDATE_CD_MODE=none
    UPDATE_MINECRAFT=0
    if [[ -n "${SELECTED[core]:-}" || -n "${SELECTED[audio-cd]:-}" || -n "${SELECTED[minecraft]:-}" ]]; then
      UPDATE_CORE=1
    fi
    if [[ -n "${SELECTED[audio-cd]:-}" ]]; then
      UPDATE_CD_MODE=presence
    elif [[ -n "${SELECTED[cd-player]:-}" ]]; then
      UPDATE_CD_MODE=player
    fi
    [[ -n "${SELECTED[minecraft]:-}" ]] && UPDATE_MINECRAFT=1
    UPDATER_TMP="$(mktemp "$BIN_DIR/.roaring-presence-update.XXXXXX")"
    cat > "$UPDATER_TMP" <<UPDATER
#!/usr/bin/env bash
set -euo pipefail
SOURCE_DIR=$SOURCE_DIR_Q
SOURCE_BRANCH=$SOURCE_BRANCH_Q
SOURCE_REMOTE=$SOURCE_REMOTE_Q
PROFILE_ARGS=($PROFILE_ARGS_Q)
UPDATE_CORE=$UPDATE_CORE
UPDATE_CD_MODE=$UPDATE_CD_MODE
UPDATE_MINECRAFT=$UPDATE_MINECRAFT
MODE=apply
case "\${1:---apply}" in
  --check) MODE=check ;;
  --apply) MODE=apply ;;
  -h|--help)
    echo 'Usage: roaring-presence-update [--check|--apply]'
    echo 'Fetch the installed Git branch from GitHub, verify it in a temporary worktree, test, reinstall, and refresh active sessions.'
    exit 0
    ;;
  *) echo "unknown option: \$1" >&2; exit 2 ;;
esac
if [[ ! -d "\$SOURCE_DIR/.git" ]]; then
  echo "source checkout missing: \$SOURCE_DIR (reinstall from a Git clone to restore updates)" >&2
  exit 1
fi
CURRENT_REMOTE="\$(git -C "\$SOURCE_DIR" remote get-url origin)"
if [[ "\$CURRENT_REMOTE" != "\$SOURCE_REMOTE" ]]; then
  echo "origin remote changed; refusing to update from an unexpected source" >&2
  exit 1
fi
if [[ -n "\$(git -C "\$SOURCE_DIR" status --porcelain)" ]]; then
  echo "source checkout has local changes; commit or stash them before updating" >&2
  exit 1
fi
git -C "\$SOURCE_DIR" fetch --quiet origin "\$SOURCE_BRANCH"
REMOTE_SHA="\$(git -C "\$SOURCE_DIR" rev-parse FETCH_HEAD)"
LOCAL_SHA="\$(git -C "\$SOURCE_DIR" rev-parse HEAD)"
if ! git -C "\$SOURCE_DIR" merge-base --is-ancestor "\$LOCAL_SHA" "\$REMOTE_SHA"; then
  echo "local checkout has diverged from GitHub; refusing a non-fast-forward update" >&2
  exit 1
fi
if [[ "\$MODE" == check ]]; then
  if [[ "\$LOCAL_SHA" == "\$REMOTE_SHA" ]]; then
    echo "up to date: \$LOCAL_SHA"
  else
    echo "update available: \$LOCAL_SHA -> \$REMOTE_SHA"
  fi
  exit 0
fi
if [[ "\$LOCAL_SHA" == "\$REMOTE_SHA" ]]; then
  echo "already at GitHub commit \$REMOTE_SHA; reinstalling the selected profile"
else
  echo "verifying candidate commit \$REMOTE_SHA before updating"
  VERIFY_DIR="\$(mktemp -d)"
  cleanup() {
    cd "\$SOURCE_DIR" 2>/dev/null || true
    git -C "\$SOURCE_DIR" worktree remove --force "\$VERIFY_DIR" >/dev/null 2>&1 || true
    rmdir "\$VERIFY_DIR" 2>/dev/null || true
  }
  trap cleanup EXIT
  git -C "\$SOURCE_DIR" worktree add --quiet --detach "\$VERIFY_DIR" "\$REMOTE_SHA"
  cd "\$VERIFY_DIR"
  python3 -m py_compile \\
    core/bin/roaring-presenced core/bin/roaring-presence-doctor \\
    providers/audio-cd/bin/roaring-cd-presence \\
    providers/audio-cd/bin/roaring-cd-session \
    providers/audio-cd/bin/roaring-cd-autoplay \\
    providers/audio-cd/bin/roaring-cd-player \\
    providers/audio-cd/bin/cd_paths.py \
    providers/minecraft/bin/roaring-minecraft-presence \\
    tools/assets/bin/roaring-presence-art.py \\
    tools/assets/bin/roaring-presence-assets tests/test_regressions.py
  python3 -m unittest discover -s tests -v
  bash -n install.sh providers/audio-cd/bin/roaring-presence-scan
  cd "\$SOURCE_DIR"
  git -C "\$SOURCE_DIR" merge --ff-only "\$REMOTE_SHA"
  cleanup
  trap - EXIT
fi
cd "\$SOURCE_DIR"
# Re-run the quick checks on the exact tree that will be installed.
python3 -m py_compile \\
  core/bin/roaring-presenced core/bin/roaring-presence-doctor \\
  providers/audio-cd/bin/roaring-cd-presence \\
  providers/audio-cd/bin/roaring-cd-session \
  providers/audio-cd/bin/roaring-cd-autoplay \\
  providers/audio-cd/bin/roaring-cd-player \\
  providers/audio-cd/bin/cd_paths.py \
  providers/minecraft/bin/roaring-minecraft-presence \\
  tools/assets/bin/roaring-presence-art.py \\
  tools/assets/bin/roaring-presence-assets tests/test_regressions.py
python3 -m unittest discover -s tests -v
bash -n install.sh providers/audio-cd/bin/roaring-presence-scan
export XDG_RUNTIME_DIR="\${XDG_RUNTIME_DIR:-/run/user/\$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="\${DBUS_SESSION_BUS_ADDRESS:-unix:path=\$XDG_RUNTIME_DIR/bus}"
"\$SOURCE_DIR/install.sh" "\${PROFILE_ARGS[@]}"
# Refresh only services that belong to the installed profile.
if [[ "\$UPDATE_CORE" == 1 ]] && systemctl --user is-active --quiet roaring-presenced.service 2>/dev/null; then
  systemctl --user restart roaring-presenced.service
fi
if [[ "\$UPDATE_CD_MODE" == player ]]; then
  CD_UNIT_GLOB='roaring-cd-player@*.service'
elif [[ "\$UPDATE_CD_MODE" == presence ]]; then
  CD_UNIT_GLOB='roaring-cd-presence@*.service'
else
  CD_UNIT_GLOB=''
fi
if [[ -n "\$CD_UNIT_GLOB" ]]; then
  mapfile -t ACTIVE_CD_UNITS < <(
    systemctl --user list-units --state=active --plain --no-legend \
      "\$CD_UNIT_GLOB" 2>/dev/null | awk '{print \$1}'
  )
  for unit in "\${ACTIVE_CD_UNITS[@]}"; do
    systemctl --user restart "\$unit"
  done
fi
if [[ "\$UPDATE_MINECRAFT" == 1 ]] && systemctl --user is-active --quiet roaring-minecraft-presence.service 2>/dev/null; then
  systemctl --user restart roaring-minecraft-presence.service
fi
echo "updated to GitHub commit \$(git rev-parse --short HEAD); active sessions refreshed"
UPDATER
    chmod 755 "$UPDATER_TMP"
    # Atomic replacement is important when this installer is invoked by the
    # updater itself: the running shell keeps its old file descriptor while
    # future invocations see the newly generated script.
    if ! cmp -s "$UPDATER_TMP" "$BIN_DIR/roaring-presence-update" 2>/dev/null; then
      mv -f "$UPDATER_TMP" "$BIN_DIR/roaring-presence-update"
    else
      rm -f "$UPDATER_TMP"
    fi
    if [[ -d "$HOME/bin" ]]; then
      ln -sfn "$BIN_DIR/roaring-presence-update" "$HOME/bin/roaring-presence-update"
    fi
  fi
fi

# The old bridge only served the superseded standalone Minecraft RPC program.
# Removing it is explicit so installation never interrupts an existing session.
if [[ -n "${SELECTED[core]:-}" || "$HAS_CD" -eq 1 || -n "${SELECTED[minecraft]:-}" || "$REMOVE_LEGACY_BRIDGE" -eq 1 ]]; then
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
      if [[ "$PLAYER_ONLY_CD" -eq 1 ]]; then
        systemctl --user enable roaring-cd-player-scan.service
      else
        systemctl --user enable roaring-cd-presence-scan.service
      fi
    fi
    if [[ "$REMOVE_LEGACY_BRIDGE" -eq 1 ]]; then
      systemctl --user disable --now discord-rpc-bridge.service 2>/dev/null || true
      rm -f "$CONFIG_ROOT/systemd/user/discord-rpc-bridge.service"
      systemctl --user daemon-reload
      echo "removed legacy discord-rpc-bridge.service"
    elif systemctl --user is-enabled --quiet discord-rpc-bridge.service 2>/dev/null; then
      echo "note: obsolete discord-rpc-bridge.service is still enabled."
      echo "      Remove with: ./install.sh --remove-legacy-bridge"
    fi
  fi
fi

echo
echo "Installed components:"
for component in cd-player audio-cd core minecraft assets; do
  if [[ -n "${SELECTED[$component]:-}" ]]; then echo "  - $component"; fi
done
echo "  binaries: $BIN_DIR"
if [[ "$HAS_CD" -eq 1 ]]; then
  echo
  if [[ "$PLAYER_ONLY_CD" -eq 1 ]]; then
    echo "CD player-only mode: no Discord core, client, or Application ID required."
    echo "Optional automatic insert activation (requires root once):"
    echo "  sudo install -m 644 $HERE/providers/audio-cd/udev/99-roaring-cd-player.rules /etc/udev/rules.d/"
  else
    echo "Discord-enabled CD mode: playback is included; the core publishes presence."
    echo "Optional automatic insert activation (requires root once):"
    echo "  sudo install -m 644 $HERE/providers/audio-cd/udev/99-roaring-presence-cd.rules /etc/udev/rules.d/"
  fi
  echo "  sudo udevadm control --reload"
  if [[ "$ENABLE_LOGIN_SCAN" -eq 0 ]]; then
    echo "Optional one-shot login catch-up scan: ./install.sh --enable-login-scan"
  fi
fi
if [[ -n "${SELECTED[core]:-}" || -n "${SELECTED[audio-cd]:-}" || -n "${SELECTED[minecraft]:-}" ]]; then
  echo
  echo "Run: $BIN_DIR/roaring-presence-doctor"
fi
if [[ -x "$BIN_DIR/roaring-presence-update" ]]; then
  echo "Update from the same GitHub branch later with: $BIN_DIR/roaring-presence-update"
fi
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo "note: $BIN_DIR is not on this shell's PATH; desktop launchers and services use absolute paths."
  echo "      Add it to your shell PATH to use command names without a full path."
fi
if [[ -n "${SELECTED[assets]:-}" ]]; then
  echo "Asset tools: $BIN_DIR/roaring-presence-assets --help"
fi
if [[ -z "${SELECTED[core]:-}" && "$HAS_CD" -eq 0 && -z "${SELECTED[assets]:-}" && "$REMOVE_LEGACY_BRIDGE" -eq 1 ]]; then
  echo "Legacy bridge cleanup-only mode; no components were installed."
fi
