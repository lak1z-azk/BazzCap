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
APPDIR="$DIST_DIR/AppDir"
PYI_DIST="$DIST_DIR/pyinstaller"
PYI_BUILD="$ROOT_DIR/build/pyinstaller"
ICON_SRC="$ROOT_DIR/bazzcap/resources/bazzcap.svg"
ICON_PNG="$ROOT_DIR/bazzcap/resources/bazzcap.png"
DESKTOP_SRC="$ROOT_DIR/bazzcap.desktop"
APPIMAGE_TOOL="$ROOT_DIR/build/appimagetool.AppImage"
OUTPUT_APPIMAGE="$DIST_DIR/${APP_NAME}-${VERSION}-x86_64.AppImage"

rm -rf "$APPDIR" "$PYI_DIST" "$PYI_BUILD"
mkdir -p "$DIST_DIR" "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
  "$APPDIR/usr/share/icons/hicolor/scalable/apps" \
  "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
  "$ROOT_DIR/build"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt pyinstaller

pyinstaller \
  --noconfirm \
  --clean \
  --onedir \
  --windowed \
  --name "$APP_NAME" \
  --icon "$ICON_SRC" \
  --add-data "$ICON_SRC:bazzcap/resources" \
  --add-data "$ICON_PNG:bazzcap/resources" \
  --add-data "$ROOT_DIR/bazzcap/_portal_helper.py:bazzcap" \
  --add-data "$ROOT_DIR/bazzcap/_trigger.py:bazzcap" \
  bazzcap.py \
  --distpath "$PYI_DIST" \
  --workpath "$PYI_BUILD"

cp -r "$PYI_DIST/$APP_NAME" "$APPDIR/usr/bin/$APP_NAME"
cp "$DESKTOP_SRC" "$APPDIR/$APP_NAME.desktop"
cp "$DESKTOP_SRC" "$APPDIR/usr/share/applications/$APP_NAME.desktop"
cp "$ICON_SRC" "$APPDIR/$APP_NAME.svg"
cp "$ICON_SRC" "$APPDIR/bazzcap.svg"
cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/scalable/apps/bazzcap.svg"
cp "$ICON_PNG" "$APPDIR/bazzcap.png"
cp "$ICON_PNG" "$APPDIR/usr/share/icons/hicolor/256x256/apps/bazzcap.png"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/BazzCap/BazzCap" "$@"
EOF
chmod +x "$APPDIR/AppRun"

sed -i "s|^Exec=.*|Exec=BazzCap|g" "$APPDIR/$APP_NAME.desktop" "$APPDIR/usr/share/applications/$APP_NAME.desktop"
sed -i "s|^Icon=.*|Icon=bazzcap|g" "$APPDIR/$APP_NAME.desktop" "$APPDIR/usr/share/applications/$APP_NAME.desktop"

rm -f "$OUTPUT_APPIMAGE"

if [ ! -f "$APPIMAGE_TOOL" ]; then
  if command -v appimagetool >/dev/null 2>&1; then
    APPIMAGE_TOOL="$(command -v appimagetool)"
  else
    echo "ERROR: appimagetool not found."
    echo "Install appimagetool system-wide or place it at: $ROOT_DIR/build/appimagetool.AppImage"
    exit 1
  fi
fi

ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGE_TOOL" "$APPDIR" "$OUTPUT_APPIMAGE"

printf "%s\n" "$OUTPUT_APPIMAGE"
