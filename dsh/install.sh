#!/bin/bash
# install.sh — Install / update the DSH web background service + menu bar app.
# Rehydratable: derives paths and labels from the current user, no hardcoded identities.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_HOME="$HOME"
USER_NAME="$(whoami)"
USER_UID="$(id -u)"

# ---- resolve dsh + node bin (must match what setup-web-profile.sh installed) ----
DSH_BIN="$(command -v dsh || true)"
if [ -z "$DSH_BIN" ]; then
    echo "ERROR: dsh not on PATH. Run ./scripts/setup-web-profile.sh first (or npm i -g @deepseek-ai/dsh)."
    exit 1
fi
NODE_BIN="$(dirname "$DSH_BIN")"

LABEL="com.$USER_NAME.dsh-web"
PLIST_SRC_TMPL="$REPO_DIR/launchagent/dsh-web.plist.tpl"
PLIST_DST="$USER_HOME/Library/LaunchAgents/$LABEL.plist"
MENUBAR_SRC="$REPO_DIR/menubar/dsh-menubar.swift"

log() { printf '\n==> %s\n' "$*"; }

log "Resolved"
echo "   dsh:      $DSH_BIN"
echo "   node bin: $NODE_BIN"
echo "   label:    $LABEL"

# ---------------------------------------------------------------------------
log "1. Stopping any manually-running dsh web instance (frees port 3080)"
pkill -f "dsh web" 2>/dev/null || true
pkill -f "@deepseek-ai/dsh web" 2>/dev/null || true

# ---------------------------------------------------------------------------
log "2. Installing LaunchAgent plist"
mkdir -p "$USER_HOME/Library/LaunchAgents"
sed -e "s|__LABEL__|$LABEL|g" \
    -e "s|__DSH_BIN__|$DSH_BIN|g" \
    -e "s|__USER_HOME__|$USER_HOME|g" \
    -e "s|__NODE_BIN__|$NODE_BIN|g" \
    "$PLIST_SRC_TMPL" > "$PLIST_DST"
chmod 644 "$PLIST_DST"
echo "   Wrote $PLIST_DST"

log "   Unloading any existing instance, then loading the service"
launchctl bootout "gui/$USER_UID/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$USER_UID" "$PLIST_DST"
launchctl enable "gui/$USER_UID/$LABEL"
launchctl kickstart -k "gui/$USER_UID/$LABEL"
echo "   Service label: $LABEL"
echo "   Web UI:        http://127.0.0.1:3080/"

# ---------------------------------------------------------------------------
log "3. Building the menu bar app"
APP_NAME="DSH Menu Bar.app"
APP_DIR="$USER_HOME/Applications/$APP_NAME"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
rm -rf "$APP_DIR"
mkdir -p "$MACOS" "$RESOURCES"

sed -e "s|__LABEL__|$LABEL|g" "$MENUBAR_SRC" > "$MACOS/dsh-menubar.swift.tmp"
swiftc -O "$MACOS/dsh-menubar.swift.tmp" -o "$MACOS/dsh-menubar"
rm -f "$MACOS/dsh-menubar.swift.tmp"

cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>DSH Menu Bar</string>
    <key>CFBundleDisplayName</key>
    <string>DSH Menu Bar</string>
    <key>CFBundleIdentifier</key>
    <string>$LABEL.menubar</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>dsh-menubar</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST
chmod +x "$MACOS/dsh-menubar"
echo "   Installed to: $APP_DIR"

# ---------------------------------------------------------------------------
log "4. Adding the menu bar app to login items"
if osascript -e "tell application \"System Events\" to get the name of every login item" | grep -q "DSH Menu Bar"; then
    echo "   Already a login item; skipping"
else
    osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$APP_DIR\", hidden:true}"
    echo "   Added as a login item (starts automatically after login)"
fi

# ---------------------------------------------------------------------------
log "5. Opening the menu bar icon now"
open "$APP_DIR" || true

echo
echo "All done!"
echo "  - Web service running at  http://127.0.0.1:3080/"
echo "  - A green 'DSH' menu bar icon is now in the top-right."
echo "  - It will start automatically at login."
echo
echo "Manage the service with:"
echo "    launchctl kickstart -k gui/$USER_UID/$LABEL   # restart"
echo "    launchctl print     gui/$USER_UID/$LABEL      # status"
echo "    launchctl bootout   gui/$USER_UID/$LABEL      # stop"
