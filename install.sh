#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="BazzCap"
INSTALL_DIR="$HOME/.local/share/bazzcap"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

if [[ "${1:-}" == "--uninstall" ]]; then
    echo "═══════════════════════════════════════════"
    echo "   Uninstalling $APP_NAME"
    echo "═══════════════════════════════════════════"
    echo

    if command -v gsettings &>/dev/null; then
        SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
        EXISTING=$(gsettings get "$SCHEMA" custom-keybindings 2>/dev/null || echo "@as []")
        for name in capture_region capture_fullscreen capture_window; do
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

    for name in capture_region capture_fullscreen capture_window; do
        rm -f "$DESKTOP_DIR/bazzcap-${name}.desktop"
    done
    KWRITE=""
    command -v kwriteconfig6 &>/dev/null && KWRITE="kwriteconfig6"
    [ -z "$KWRITE" ] && command -v kwriteconfig5 &>/dev/null && KWRITE="kwriteconfig5"
    if [ -n "$KWRITE" ]; then
        for name in capture_region capture_fullscreen capture_window; do
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

echo "═══════════════════════════════════════════"
echo "   $APP_NAME Installer"
echo "   Screenshot Tool for Linux"
echo "═══════════════════════════════════════════"
echo

PKG_MGR=""
IMMUTABLE=false
NEED_REBOOT=false

if command -v rpm-ostree &>/dev/null && ostree admin status &>/dev/null 2>&1; then
    PKG_MGR="rpm-ostree"
    IMMUTABLE=true
elif command -v dnf &>/dev/null; then
    PKG_MGR="dnf"
elif command -v apt-get &>/dev/null; then
    PKG_MGR="apt"
elif command -v pacman &>/dev/null; then
    PKG_MGR="pacman"
elif command -v zypper &>/dev/null; then
    PKG_MGR="zypper"
fi

echo "  Package manager: ${PKG_MGR:-none detected}"
if $IMMUTABLE; then
    echo "  Immutable system detected (rpm-ostree)"
fi
echo

install_if_missing() {
    local cmd="$1"
    local pkg_dnf="$2"
    local pkg_apt="$3"
    local pkg_pacman="$4"
    local pkg_zypper="${5:-$pkg_dnf}"
    local purpose="$6"

    if command -v "$cmd" &>/dev/null; then
        echo "  ✓ $cmd (already installed)"
        return 0
    fi

    echo "  → $cmd not found ($purpose). Installing..."

    case "$PKG_MGR" in
        rpm-ostree)
            sudo rpm-ostree install -y --allow-inactive "$pkg_dnf" 2>/dev/null && \
                NEED_REBOOT=true && echo "  ✓ $pkg_dnf queued (reboot needed)" || \
                echo "  ⚠ Could not install $pkg_dnf via rpm-ostree"
            ;;
        dnf)
            sudo dnf install -y "$pkg_dnf" 2>/dev/null && \
                echo "  ✓ $pkg_dnf installed" || \
                echo "  ⚠ Could not install $pkg_dnf"
            ;;
        apt)
            sudo apt-get install -y "$pkg_apt" 2>/dev/null && \
                echo "  ✓ $pkg_apt installed" || \
                echo "  ⚠ Could not install $pkg_apt"
            ;;
        pacman)
            sudo pacman -S --noconfirm "$pkg_pacman" 2>/dev/null && \
                echo "  ✓ $pkg_pacman installed" || \
                echo "  ⚠ Could not install $pkg_pacman"
            ;;
        zypper)
            sudo zypper install -y "$pkg_zypper" 2>/dev/null && \
                echo "  ✓ $pkg_zypper installed" || \
                echo "  ⚠ Could not install $pkg_zypper"
            ;;
        *)
            echo "  ⚠ No supported package manager found. Please install $pkg_dnf manually."
            return 1
            ;;
    esac
}

echo "[1/8] Checking Python 3..."
if ! command -v python3 &>/dev/null; then
    echo "  → Python 3 not found. Attempting to install..."
    case "$PKG_MGR" in
        rpm-ostree) sudo rpm-ostree install -y --allow-inactive python3 python3-libs 2>/dev/null; NEED_REBOOT=true ;;
        dnf)  sudo dnf install -y python3 python3-libs 2>/dev/null ;;
        apt)  sudo apt-get install -y python3 python3-venv python3-pip 2>/dev/null ;;
        pacman) sudo pacman -S --noconfirm python 2>/dev/null ;;
        zypper) sudo zypper install -y python3 2>/dev/null ;;
        *)    echo "  ✗ Cannot install Python 3 automatically. Please install it manually."; exit 1 ;;
    esac
fi

if ! command -v python3 &>/dev/null; then
    echo "  ✗ Python 3 is still not available."
    if $NEED_REBOOT; then
        echo "  → A reboot may be required for rpm-ostree changes to take effect."
        echo "  → Reboot and re-run: bash install.sh"
    fi
    exit 1
fi
PYTHON_VER=$(python3 --version 2>&1)
echo "  ✓ $PYTHON_VER"

if ! python3 -m venv --help &>/dev/null 2>&1; then
    echo "  → venv module not found. Installing..."
    case "$PKG_MGR" in
        rpm-ostree) sudo rpm-ostree install -y --allow-inactive python3-libs 2>/dev/null; NEED_REBOOT=true ;;
        dnf)  sudo dnf install -y python3-libs 2>/dev/null ;;
        apt)  sudo apt-get install -y python3-venv 2>/dev/null ;;
        pacman) echo "  → venv is included with python on Arch" ;;
        zypper) sudo zypper install -y python3-venv 2>/dev/null ;;
    esac
    if ! python3 -m venv --help &>/dev/null 2>&1; then
        if $NEED_REBOOT; then
            echo "  → Reboot required for rpm-ostree changes, then re-run installer."
            exit 1
        fi
        echo "  ✗ python3-venv still not available."
        exit 1
    fi
fi
echo "  ✓ venv module available"

echo
echo "[2/8] Installing system dependencies..."

DE=$(echo "${XDG_CURRENT_DESKTOP:-}" | tr '[:upper:]' '[:lower:]')

install_if_missing "xdotool" "xdotool" "xdotool" "xdotool" "xdotool" \
    "cursor position detection on Wayland"

install_if_missing "wl-copy" "wl-clipboard" "wl-clipboard" "wl-clipboard" "wl-clipboard" \
    "clipboard support on Wayland"

if [[ "$DE" == *"kde"* ]] || [[ "$DE" == *"plasma"* ]]; then
    install_if_missing "spectacle" "spectacle" "kde-spectacle" "spectacle" "spectacle" \
        "KDE screenshot backend"
else
    install_if_missing "grim" "grim" "grim" "grim" "grim" \
        "Wayland screenshot backend"
fi

install_if_missing "notify-send" "libnotify" "libnotify-bin" "libnotify" "libnotify-tools" \
    "desktop notifications"

if $NEED_REBOOT; then
    echo
    echo "  ═══════════════════════════════════════════"
    echo "  ⚠ Some packages were queued via rpm-ostree."
    echo "    A REBOOT is required before they become available."
    echo "    After rebooting, re-run:  bash install.sh"
    echo "  ═══════════════════════════════════════════"
    echo
    read -p "  Continue installing BazzCap anyway? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        exit 0
    fi
fi

echo
echo "[3/8] Copying app files to $INSTALL_DIR..."

mkdir -p "$INSTALL_DIR"

rm -rf "$INSTALL_DIR/bazzcap"
rm -f "$INSTALL_DIR/bazzcap.py"
rm -f "$INSTALL_DIR/requirements.txt"

cp -r "$SCRIPT_DIR/bazzcap" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/bazzcap.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"

find "$INSTALL_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

echo "  ✓ App files installed"

echo
echo "[4/8] Setting up Python virtual environment..."

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

echo
echo "[5/8] Installing icon..."

mkdir -p "$ICON_DIR"
if [ -f "$INSTALL_DIR/bazzcap/resources/bazzcap.svg" ]; then
    cp "$INSTALL_DIR/bazzcap/resources/bazzcap.svg" "$ICON_DIR/bazzcap.svg"
    echo "  ✓ Icon installed"
else
    echo "  ⚠ Icon file not found, using fallback"
fi

gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo
echo "[6/8] Creating launcher and desktop entry..."

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

mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/bazzcap.desktop" << DESKTOP
[Desktop Entry]
Name=BazzCap
Comment=Screenshot Tool for Linux
Exec=$BIN_DIR/bazzcap
Icon=bazzcap
Terminal=false
Type=Application
Categories=Utility;Graphics;
Keywords=screenshot;capture;annotation;screen;
StartupNotify=false
StartupWMClass=bazzcap
DESKTOP
chmod +x "$DESKTOP_DIR/bazzcap.desktop"
echo "  ✓ Desktop entry installed"

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo
echo "[7/8] Setting up autostart..."

mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/bazzcap.desktop" << AUTOSTART
[Desktop Entry]
Name=BazzCap
Comment=Screenshot Tool
Exec=$BIN_DIR/bazzcap
Icon=bazzcap
Terminal=false
Type=Application
X-GNOME-Autostart-enabled=true
Hidden=false
AUTOSTART
echo "  ✓ Autostart enabled (BazzCap will start on login)"
echo "    You can disable this in BazzCap Settings > 'Start with system'"

echo
echo "[8/8] Checking PATH..."

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "  → $BIN_DIR is not in your PATH."
    if ! grep -q 'export PATH="\$HOME/.local/bin:\$PATH"' "$HOME/.bashrc" 2>/dev/null; then
        echo '' >> "$HOME/.bashrc"
        echo '# Added by BazzCap installer' >> "$HOME/.bashrc"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        echo "  ✓ Added ~/.local/bin to PATH in ~/.bashrc"
    else
        echo "  ✓ PATH entry already in ~/.bashrc"
    fi
    export PATH="$BIN_DIR:$PATH"
    echo "  ✓ PATH updated for current session"
else
    echo "  ✓ $BIN_DIR is already in PATH"
fi

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
echo "  Starting BazzCap now..."
echo
nohup "$BIN_DIR/bazzcap" > /dev/null 2>&1 & disown
echo "  ✓ BazzCap is running in the system tray!"

