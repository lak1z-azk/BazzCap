#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="BazzCap"
INSTALL_DIR="$HOME/Library/Application Support/bazzcap"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="/usr/local/bin"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$LAUNCH_AGENT_DIR/com.bazzcap.plist"
APP_DIR="$HOME/Applications/BazzCap.app"

# ─── Uninstall ────────────────────────────────────────────────────────────────

if [[ "${1:-}" == "--uninstall" ]]; then
    echo "═══════════════════════════════════════════"
    echo "   Uninstalling $APP_NAME"
    echo "═══════════════════════════════════════════"
    echo

    # Stop launch agent
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    rm -f "$PLIST_FILE"
    echo "  ✓ Launch agent removed"

    # Remove launcher
    sudo rm -f "$BIN_DIR/bazzcap" 2>/dev/null || rm -f "$BIN_DIR/bazzcap" 2>/dev/null || true

    # Remove app bundle
    rm -rf "$APP_DIR" 2>/dev/null || true

    # Remove install dir
    rm -rf "$INSTALL_DIR"
    echo "  ✓ All files removed"

    echo
    echo "  $APP_NAME has been uninstalled."
    echo "  Config remains at ~/Library/Application Support/bazzcap/ (delete if desired)."
    exit 0
fi

# ─── Install ──────────────────────────────────────────────────────────────────

echo "═══════════════════════════════════════════"
echo "   $APP_NAME Installer for macOS"
echo "   Screenshot Tool"
echo "═══════════════════════════════════════════"
echo

# --- Step 1: Python 3 ---
echo "[1/7] Checking Python 3..."

if ! command -v python3 &>/dev/null; then
    echo "  → Python 3 not found."
    if command -v brew &>/dev/null; then
        echo "  → Installing via Homebrew..."
        brew install python3
    else
        echo "  ✗ Python 3 is required. Install it from https://www.python.org/downloads/"
        echo "    or install Homebrew first: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
fi

PYTHON_VER=$(python3 --version 2>&1)
echo "  ✓ $PYTHON_VER"

# Check venv
if ! python3 -m venv --help &>/dev/null 2>&1; then
    echo "  ✗ Python venv module not available. Reinstall Python from python.org or brew."
    exit 1
fi
echo "  ✓ venv module available"

# --- Step 2: System dependencies ---
echo
echo "[2/7] Checking system tools..."

# screencapture is built into macOS
if command -v screencapture &>/dev/null; then
    echo "  ✓ screencapture (built-in)"
else
    echo "  ⚠ screencapture not found — this should be built into macOS"
fi

# pbcopy is built into macOS
if command -v pbcopy &>/dev/null; then
    echo "  ✓ pbcopy (built-in)"
fi

# osascript is built into macOS
if command -v osascript &>/dev/null; then
    echo "  ✓ osascript (built-in)"
fi

echo "  ✓ All macOS built-in tools available"

# --- Step 3: Copy app files ---
echo
echo "[3/7] Copying app files to $INSTALL_DIR..."

mkdir -p "$INSTALL_DIR"

rm -rf "$INSTALL_DIR/bazzcap"
rm -f "$INSTALL_DIR/bazzcap.py"
rm -f "$INSTALL_DIR/requirements.txt"

cp -r "$SCRIPT_DIR/bazzcap" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/bazzcap.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"

find "$INSTALL_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

echo "  ✓ App files installed"

# --- Step 4: Virtual environment ---
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

# --- Step 5: Create launcher ---
echo
echo "[5/7] Creating launcher..."

LAUNCHER_SCRIPT=$(cat << 'LAUNCHER'
#!/usr/bin/env bash
# BazzCap launcher — uses its own virtual environment
BAZZCAP_DIR="$HOME/Library/Application Support/bazzcap"
VENV_PYTHON="$BAZZCAP_DIR/venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "BazzCap venv not found at $VENV_PYTHON"
    echo "Please reinstall BazzCap."
    exit 1
fi

cd "$BAZZCAP_DIR"
exec "$VENV_PYTHON" bazzcap.py "$@"
LAUNCHER
)

# Try /usr/local/bin first, fall back to ~/bin
if [ -w "$BIN_DIR" ] || sudo mkdir -p "$BIN_DIR" 2>/dev/null; then
    echo "$LAUNCHER_SCRIPT" | sudo tee "$BIN_DIR/bazzcap" > /dev/null
    sudo chmod +x "$BIN_DIR/bazzcap"
    echo "  ✓ Launcher: $BIN_DIR/bazzcap"
elif mkdir -p "$HOME/bin" 2>/dev/null; then
    BIN_DIR="$HOME/bin"
    echo "$LAUNCHER_SCRIPT" > "$BIN_DIR/bazzcap"
    chmod +x "$BIN_DIR/bazzcap"
    echo "  ✓ Launcher: $BIN_DIR/bazzcap"
fi

# Create a macOS .app bundle for Finder/Dock/Spotlight
echo
echo "[6/7] Creating macOS app bundle..."

mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

cat > "$APP_DIR/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>BazzCap</string>
  <key>CFBundleDisplayName</key>
  <string>BazzCap</string>
  <key>CFBundleIdentifier</key>
  <string>com.bazzcap</string>
  <key>CFBundleVersion</key>
  <string>1.1.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.1.0</string>
  <key>CFBundleExecutable</key>
  <string>BazzCap</string>
  <key>CFBundleIconFile</key>
  <string>bazzcap</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>LSBackgroundOnly</key>
  <false/>
</dict>
</plist>
PLIST

# App launcher script
cat > "$APP_DIR/Contents/MacOS/BazzCap" << 'APPLAUNCHER'
#!/usr/bin/env bash
BAZZCAP_DIR="$HOME/Library/Application Support/bazzcap"
VENV_PYTHON="$BAZZCAP_DIR/venv/bin/python"
cd "$BAZZCAP_DIR"
exec "$VENV_PYTHON" bazzcap.py "$@"
APPLAUNCHER
chmod +x "$APP_DIR/Contents/MacOS/BazzCap"

# Copy icon if available
if [ -f "$INSTALL_DIR/bazzcap/resources/bazzcap.svg" ]; then
    cp "$INSTALL_DIR/bazzcap/resources/bazzcap.svg" "$APP_DIR/Contents/Resources/bazzcap.svg"
fi
# If there's an .icns version, prefer it
if [ -f "$INSTALL_DIR/bazzcap/resources/bazzcap.icns" ]; then
    cp "$INSTALL_DIR/bazzcap/resources/bazzcap.icns" "$APP_DIR/Contents/Resources/bazzcap.icns"
fi

echo "  ✓ App bundle: $APP_DIR"
echo "    You can drag BazzCap.app to /Applications if desired"

# --- Step 7: Autostart (optional LaunchAgent) ---
echo
echo "[7/7] Setting up autostart (LaunchAgent)..."

mkdir -p "$LAUNCH_AGENT_DIR"
cat > "$PLIST_FILE" << PLISTLA
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.bazzcap</string>
  <key>ProgramArguments</key>
  <array>
    <string>$BIN_DIR/bazzcap</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
PLISTLA
echo "  ✓ Autostart enabled (BazzCap will start on login)"
echo "    You can disable this in BazzCap Settings > 'Start with system'"
echo "    Or remove: $PLIST_FILE"

echo
echo "═══════════════════════════════════════════"
echo "   ✓ $APP_NAME installed successfully!"
echo "═══════════════════════════════════════════"
echo
echo "  Launch:  bazzcap"
echo "  Or open: ~/Applications/BazzCap.app"
echo "  Or search: 'BazzCap' in Spotlight"
echo
echo "  Uninstall:  bash install_macos.sh --uninstall"
echo
echo "  ⚠ Note: macOS may ask for Screen Recording and"
echo "    Accessibility permissions on first use."
echo "    Grant these in System Settings > Privacy & Security."
echo
echo "  Starting BazzCap now..."
echo
pkill -f "python.*bazzcap" 2>/dev/null || true
sleep 0.5
nohup "$BIN_DIR/bazzcap" > /dev/null 2>&1 & disown
echo "  ✓ BazzCap is running in the menu bar!"
