#!/usr/bin/env bash
set -euo pipefail

DMG_PATH="${1:-$HOME/Downloads/SchoolTimer-arm64.dmg}"
MOUNT_POINT="/Volumes/SchoolTimer"
APP_NAME="SchoolTimer.app"
TMP_APP="/tmp/$APP_NAME"

if [[ ! -f "$DMG_PATH" ]]; then
  printf "DMG not found: %s\n" "$DMG_PATH" >&2
  exit 1
fi

xattr -dr com.apple.quarantine "$DMG_PATH" || true

if [[ -d "$MOUNT_POINT" ]]; then
  hdiutil detach "$MOUNT_POINT" -quiet || true
fi

hdiutil attach "$DMG_PATH" -quiet

if [[ ! -d "$MOUNT_POINT/$APP_NAME" ]]; then
  hdiutil detach "$MOUNT_POINT" -quiet || true
  printf "App bundle not found inside DMG.\n" >&2
  exit 1
fi

rm -rf "$TMP_APP"
cp -R "$MOUNT_POINT/$APP_NAME" "$TMP_APP"
hdiutil detach "$MOUNT_POINT" -quiet || true

xattr -dr com.apple.quarantine "$TMP_APP" || true

if cp -R "$TMP_APP" /Applications/ >/dev/null 2>&1; then
  TARGET_APP="/Applications/$APP_NAME"
else
  mkdir -p "$HOME/Applications"
  cp -R "$TMP_APP" "$HOME/Applications/"
  TARGET_APP="$HOME/Applications/$APP_NAME"
fi

xattr -dr com.apple.quarantine "$TARGET_APP" || true
codesign --force --deep --sign - "$TARGET_APP" >/dev/null 2>&1 || true
open -a "$TARGET_APP"

printf "Installed and launched: %s\n" "$TARGET_APP"
