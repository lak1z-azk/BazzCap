#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VERSION="$(python3 - <<'PY'
from bazzcap import __version__
print(__version__)
PY
)"

APP_NAME="BazzCap"
DIST_DIR="$ROOT_DIR/dist"
PYI_DIST="$DIST_DIR/pyinstaller"
PYI_BUILD="$ROOT_DIR/build/pyinstaller-macos"
APP_BUNDLE="$PYI_DIST/$APP_NAME.app"
DMG_TARGET="$DIST_DIR/${APP_NAME}-${VERSION}-macOS.dmg"
DMG_STAGING="$DIST_DIR/dmg-staging"

rm -rf "$PYI_DIST" "$PYI_BUILD" "$DMG_TARGET" "$DMG_STAGING"
mkdir -p "$DIST_DIR"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt pyinstaller

pyinstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name "$APP_NAME" \
  --add-data "$ROOT_DIR/bazzcap/resources/bazzcap.svg:bazzcap/resources" \
  --add-data "$ROOT_DIR/bazzcap/_portal_helper.py:bazzcap" \
  --add-data "$ROOT_DIR/bazzcap/_trigger.py:bazzcap" \
  --osx-bundle-identifier "com.mancavewasteland.bazzcap" \
  bazzcap.py \
  --distpath "$PYI_DIST" \
  --workpath "$PYI_BUILD"

# Build a drag-to-install DMG
mkdir -p "$DMG_STAGING"
cp -r "$APP_BUNDLE" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"

hdiutil create \
  -volname "$APP_NAME $VERSION" \
  -srcfolder "$DMG_STAGING" \
  -ov \
  -format UDZO \
  "$DMG_TARGET"

rm -rf "$DMG_STAGING"

printf "%s\n" "$DMG_TARGET"
