#!/usr/bin/env bash
#
# BazzCap Installer for Bazzite / Fedora-based Linux
#
# Installs BazzCap with its own virtual environment so it doesn't
# interfere with system packages. Creates a launcher, desktop entry,
# autostart entry, and app icon.
#
# Run with:  bash install.sh
# Uninstall: bash install.sh --uninstall
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="BazzCap"
INSTALL_DIR="$HOME/.local/share/bazzcap"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

# ── Uninstall ──
if [[ "${1:-}" == "--uninstall" ]]; then
    echo "═══════════════════════════════════════════"
    echo "   Uninstalling $APP_NAME"
    echo "═══════════════════════════════════════════"
    echo

    # Remove GNOME keybindings
    if command -v gsettings &>/dev/null; then
        SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
        EXISTING=$(gsettings get "$SCHEMA" custom-keybindings 2>/dev/null || echo "@as []")
        for name in capture_region capture_fullscreen capture_window start_recording start_gif; do
            P="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/bazzcap-${name}/"
            BS="${SCHEMA}.custom-keybinding:${P}"
            gsettings reset "$BS" name 2>/dev/null || true
            gsettings reset "$BS" command 2>/dev/null || true
            gsettings reset "$BS" binding 2>/dev/null || true
        done
        NEW=$(echo "$EXISTING" | python3 -c "
import sys, ast
raw = sys.stdin.read().strip()
if raw == '@as []':
    print('@as []')
else:
    try:
        lst = ast.literal_eval(raw)
        filtered = [p for p in lst if 'bazzcap' not in p]
        print('[' + ', '.join(repr(p) for p in filtered) + ']' if filtered else '@as []')
    except: print(raw)
" 2>/dev/null || echo "$EXISTING")
        gsettings set "$SCHEMA" custom-keybindings "$NEW" 2>/dev/null || true
        echo "  ✓ GNOME keybindings removed"
    fi

    # Remove KDE shortcut files
    for name in capture_region capture_fullscreen capture_window start_recording start_gif; do
        rm -f "$DESKTOP_DIR/bazzcap-${name}.desktop"
    done
    # Clean kglobalshortcutsrc entries
    KWRITE=""
    command -v kwriteconfig6 &>/dev/null && KWRITE="kwriteconfig6"
    [ -z "$KWRITE" ] && command -v kwriteconfig5 &>/dev/null && KWRITE="kwriteconfig5"
    if [ -n "$KWRITE" ]; then
        for name in capture_region capture_fullscreen capture_window start_recording start_gif; do
            $KWRITE --file kglobalshortcutsrc --group "bazzcap-${name}.desktop" --key "_launch" --delete 2>/dev/null || true
        done
        echo "  ✓ KDE shortcuts removed"
    fi

    rm -f "$BIN_DIR/bazzcap"
    rm -f "$DESKTOP_DIR/bazzcap.desktop"
    rm -f "$AUTOSTART_DIR/bazzcap.desktop"
    rm -f "$ICON_DIR/bazzcap.svg"
    rm -rf "$INSTALL_DIR"

    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

    echo "  ✓ All files removed"
    echo
    echo "  $APP_NAME has been uninstalled."
    echo "  Config remains at ~/.config/bazzcap/ (delete manually if desired)."
    exit 0
fi

# ── Install ──
echo "═══════════════════════════════════════════"
echo "   $APP_NAME Installer"
echo "   Screenshot & Recording Tool for Linux"
echo "═══════════════════════════════════════════"
echo

# ── Step 1: Check Python ──
echo "[1/7] Checking Python 3..."
if ! command -v python3 &>/dev/null; then
    echo "  ✗ Python 3 not found! Please install python3."
    exit 1
fi
PYTHON_VER=$(python3 --version 2>&1)
echo "  ✓ $PYTHON_VER"

# Check python3-venv is available
if ! python3 -m venv --help &>/dev/null 2>&1; then
    echo "  ✗ python3-venv module not found."
    echo "  Install it with:"
    echo "    sudo dnf install python3-libs   (Fedora/Bazzite)"
    echo "    sudo apt install python3-venv   (Debian/Ubuntu)"
    exit 1
fi
echo "  ✓ venv module available"

# ── Step 2: Check system tools ──
echo
echo "[2/7] Checking system tools..."

check_tool() {
    if command -v "$1" &>/dev/null; then
        echo "  ✓ $1"
        return 0
    else
        echo "  ✗ $1 — $2"
        return 1
    fi
}

WARNINGS=()

check_tool "xdotool" "needed for cursor detection on Wayland" || \
    WARNINGS+=("xdotool (cursor detection): sudo dnf install xdotool")

check_tool "ffmpeg" "needed for video recording & GIF" || \
    WARNINGS+=("ffmpeg (recording): sudo dnf install ffmpeg")

check_tool "wl-copy" "needed for clipboard on Wayland" || \
    WARNINGS+=("wl-clipboard (clipboard): sudo dnf install wl-clipboard")

# Check for screenshot backend (DE-aware)
DE=$(echo "${XDG_CURRENT_DESKTOP:-}" | tr '[:upper:]' '[:lower:]')
if [[ "$DE" == *"kde"* ]] || [[ "$DE" == *"plasma"* ]]; then
    check_tool "spectacle" "KDE screenshot backend" || \
        WARNINGS+=("spectacle (screenshots): sudo dnf install spectacle")
else
    check_tool "grim" "Wayland screenshot backend" || \
        WARNINGS+=("grim (screenshots): sudo dnf install grim")
fi

check_tool "notify-send" "desktop notifications" || true

if [ ${#WARNINGS[@]} -gt 0 ]; then
    echo
    echo "  ⚠ Recommended tools to install:"
    for w in "${WARNINGS[@]}"; do
        echo "    → $w"
    done
    echo
    read -p "  Continue anyway? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        exit 1
    fi
fi

# ── Step 3: Copy app files ──
echo
echo "[3/7] Copying app files to $INSTALL_DIR..."

mkdir -p "$INSTALL_DIR"

# Clean old install (keep venv if exists for faster upgrade)
rm -rf "$INSTALL_DIR/bazzcap"
rm -f "$INSTALL_DIR/bazzcap.py"
rm -f "$INSTALL_DIR/requirements.txt"

cp -r "$SCRIPT_DIR/bazzcap" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/bazzcap.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"

# Remove __pycache__ from install
find "$INSTALL_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

echo "  ✓ App files installed"

# ── Step 4: Create virtual environment & install deps ──
echo
echo "[4/7] Setting up Python virtual environment..."

if [ -d "$VENV_DIR" ]; then
    echo "  → Existing venv found, upgrading packages..."
else
    python3 -m venv "$VENV_DIR"
    echo "  ✓ Virtual environment created"
fi

"$VENV_DIR/bin/pip" install --upgrade pip --quiet 2>/dev/null || true
echo "  → Installing dependencies (this may take a moment)..."
"$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
echo "  ✓ Dependencies installed (PyQt6, Pillow)"

# ── Step 5: Install icon ──
echo
echo "[5/7] Installing icon..."

mkdir -p "$ICON_DIR"
if [ -f "$INSTALL_DIR/bazzcap/resources/bazzcap.svg" ]; then
    cp "$INSTALL_DIR/bazzcap/resources/bazzcap.svg" "$ICON_DIR/bazzcap.svg"
    echo "  ✓ Icon installed"
else
    echo "  ⚠ Icon file not found, using fallback"
fi

gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

# ── Step 6: Create launcher & desktop entry ──
echo
echo "[6/7] Creating launcher and desktop entry..."

mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/bazzcap" << LAUNCHER
#!/usr/bin/env bash
# BazzCap launcher — uses its own virtual environment
BAZZCAP_DIR="$INSTALL_DIR"
VENV_PYTHON="$VENV_DIR/bin/python"

if [ ! -f "\$VENV_PYTHON" ]; then
    echo "BazzCap venv not found at \$VENV_PYTHON"
    echo "Please reinstall BazzCap."
    exit 1
fi

cd "\$BAZZCAP_DIR"
exec "\$VENV_PYTHON" bazzcap.py "\$@"
LAUNCHER
chmod +x "$BIN_DIR/bazzcap"
echo "  ✓ Launcher: $BIN_DIR/bazzcap"

# Desktop entry
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/bazzcap.desktop" << DESKTOP
[Desktop Entry]
Name=BazzCap
Comment=Screenshot & Recording Tool for Linux
Exec=$BIN_DIR/bazzcap
Icon=bazzcap
Terminal=false
Type=Application
Categories=Utility;Graphics;
Keywords=screenshot;capture;recording;gif;annotation;screen;
StartupNotify=false
StartupWMClass=bazzcap
DESKTOP
chmod +x "$DESKTOP_DIR/bazzcap.desktop"
echo "  ✓ Desktop entry installed"

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

# ── Step 7: Autostart (optional) ──
echo
echo "[7/7] Autostart setup..."
read -p "  Start BazzCap automatically on login? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    mkdir -p "$AUTOSTART_DIR"
    cat > "$AUTOSTART_DIR/bazzcap.desktop" << AUTOSTART
[Desktop Entry]
Name=BazzCap
Comment=Screenshot & Recording Tool
Exec=$BIN_DIR/bazzcap
Icon=bazzcap
Terminal=false
Type=Application
X-GNOME-Autostart-enabled=true
Hidden=false
AUTOSTART
    echo "  ✓ Autostart enabled"
else
    rm -f "$AUTOSTART_DIR/bazzcap.desktop"
    echo "  → Autostart skipped"
fi

# ── Done ──
echo
echo "═══════════════════════════════════════════"
echo "   ✓ $APP_NAME installed successfully!"
echo "═══════════════════════════════════════════"
echo
echo "  Launch:     bazzcap"
echo "  Or search:  'BazzCap' in your app menu"
echo
echo "  Uninstall:  bash install.sh --uninstall"
echo
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "  ⚠ $BIN_DIR is not in your PATH."
    echo "  Add this to ~/.bashrc:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo
fi
echo "  Starting BazzCap now..."
echo
nohup "$BIN_DIR/bazzcap" > /dev/null 2>&1 & disown
echo "  ✓ BazzCap is running in the system tray!"
