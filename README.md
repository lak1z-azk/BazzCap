# BazzCap

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41cd52.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-orange.svg)]()
[![Platform: macOS](https://img.shields.io/badge/Platform-macOS-lightgrey.svg)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

A free and open-source screenshot tool for **Linux** and **macOS**, built with Python and PyQt6. Designed for Bazzite, Fedora, and other Linux distributions running GNOME or KDE on Wayland (X11 also supported). Also works on macOS 11+ (Big Sur and later).

BazzCap lives in the system tray and provides global hotkeys for region capture, fullscreen capture, and window capture -- with annotation tools built directly into the capture overlay.

> **BazzCap is open-source and built for the community.** Contributions, bug reports, and feature requests are welcome from everyone. See [Contributing](#contributing) to get involved.

<img width="752" height="591" alt="image" src="https://github.com/user-attachments/assets/ce59c8a1-b8ad-4c91-97c4-adc391cd294c" />

---

## Features

### Capture Modes
- **Region Capture** -- Select a rectangular area of the screen with a crosshair overlay and magnifier for precision.
- **Fullscreen Capture** -- Instantly capture the entire screen (multi-monitor aware).
- **Window Capture** -- Capture the currently focused window.

### Annotation Tools
When capturing a region, an overlay appears across the full screen. You can draw annotations directly on screen before selecting the capture area. The following tools are available in the overlay toolbar:

- **Arrow** -- Draw arrows to point at things.
- **Rectangle** -- Draw outlined rectangles.
- **Filled Rectangle** -- Draw solid filled rectangles.
- **Ellipse** -- Draw outlined ellipses.
- **Line** -- Draw straight lines.
- **Freehand** -- Draw freeform lines.
- **Text** -- Click to place text with a formatting dialog (font family, size, bold, italic, curved/arc text).
- **Blur** -- Blur a rectangular region to hide sensitive content. Blur intensity is adjustable via a slider in the toolbar.
- **Highlight** -- Draw translucent highlights over content.
- **Numbered** -- Place numbered circles (auto-incrementing) with auto-contrast text color.

<img width="698" height="55" alt="image" src="https://github.com/user-attachments/assets/28d9a4f5-dd5b-40d9-9b6f-3b77348d295d" />

All annotations can be dragged to reposition them after placement. Hover over an annotation and press DEL to remove it. After selecting a region, the annotated screenshot is saved automatically and copied to the clipboard.

### History Editor
Double-clicking a capture in the history list opens a full image editor where you can draw additional annotations (rectangle, ellipse, line, arrow, freehand, text, blur, highlight, numbered steps), crop the image, copy to clipboard, or save to a new file.

### Hotkeys
Global keyboard shortcuts are registered with your desktop environment (GNOME or KDE on Linux, pynput on macOS) so they work even when BazzCap is not focused.

**Linux defaults:**

| Action             | Default Hotkey |
|--------------------|----------------|
| Fullscreen Capture | Print          |
| Region Capture     | Ctrl+Print     |
| Window Capture     | Alt+Print      |

**macOS defaults:**

| Action             | Default Hotkey   |
|--------------------|------------------|
| Fullscreen Capture | Cmd+Shift+1      |
| Region Capture     | Cmd+Shift+2      |
| Window Capture     | Cmd+Shift+W      |

> **⚠️ Known Issue:** Global hotkeys are currently **not working on macOS**. This is under investigation. For now, use the system tray icon or the buttons in the main window to start captures. Hotkeys work normally on Linux.

Hotkeys are fully customizable from the settings dialog inside BazzCap.

### System Tray
BazzCap runs in the system tray. Right-click the tray icon to quickly start a capture, open settings, configure hotkeys, or quit. Double-click the tray icon to open the main window. Middle-click to start a region capture instantly. The main window can be minimized to tray on close.

### Desktop Integration
- **GNOME** (Linux): Hotkeys are registered as custom keybindings via gsettings.
- **KDE Plasma** (Linux): Hotkeys are registered via .desktop shortcut files and kglobalaccel D-Bus.
- **macOS**: Hotkeys use pynput (requires Accessibility permission). Autostart via LaunchAgent.
- **Autostart**: Optional autostart on login via XDG autostart (Linux) or LaunchAgent (macOS).
- **Clipboard**: Captures are automatically copied to the clipboard using wl-copy (Wayland), xclip (X11), osascript/pbcopy (macOS), or Qt clipboard as fallback.
- **Notifications**: Desktop notifications on capture completion via notify-send (Linux) or osascript (macOS).

---

## Requirements

### System
- **Linux** (tested on Bazzite / Fedora, should work on any distribution)
  - Python 3.10 or newer
  - GNOME or KDE Plasma desktop environment (for global hotkeys)
  - Wayland or X11 display server
- **macOS** 11+ (Big Sur or later)
  - Python 3.10 or newer (from python.org or Homebrew)
  - Screen Recording permission (for screenshots)
  - Accessibility permission (for global hotkeys)

### Required System Packages

#### Linux
The installer will **automatically install** all of these using your system package manager (dnf, apt, pacman, zypper, or rpm-ostree). You will be prompted for your sudo password during installation.

If you prefer to install them manually beforehand:

**Fedora / Bazzite:**
```
sudo dnf install python3 python3-libs xdotool wl-clipboard grim libnotify
```

**Debian / Ubuntu:**
```
sudo apt install python3 python3-venv python3-pip xdotool wl-clipboard grim libnotify-bin
```

**Arch Linux:**
```
sudo pacman -S python xdotool wl-clipboard grim libnotify
```

**KDE users:** Replace `grim` with `spectacle` (or `kde-spectacle` on Debian/Ubuntu).

| Package        | Purpose                          |
|----------------|----------------------------------|
| python3        | Application runtime              |
| python3-venv   | Virtual environment support      |
| xdotool        | Cursor position detection        |
| wl-clipboard   | Clipboard support on Wayland     |
| grim           | Screenshot backend (GNOME/Wayland) |
| spectacle      | Screenshot backend (KDE)         |
| libnotify      | Desktop notifications            |

#### macOS
macOS ships with all required system tools built-in (`screencapture`, `pbcopy`, `osascript`). You only need Python 3:

```
brew install python3
```

Or download from [python.org](https://www.python.org/downloads/).

### Python Dependencies
These are installed automatically inside a virtual environment by the installer:
- PyQt6 >= 6.5.0
- Pillow >= 9.0.0

---

## Installation

### Linux — Quick Install (Recommended)

Everything is handled by the installer. Just clone and run:

```
git clone https://github.com/lak1z-azk/BazzCap.git
cd BazzCap
bash install.sh
```

The installer will:
1. Detect your package manager (dnf, apt, pacman, zypper, or rpm-ostree).
2. Install all missing system dependencies automatically (sudo required).
3. Set up Python 3 and the venv module if not present.
4. Copy BazzCap files to `~/.local/share/bazzcap/`.
5. Create an isolated Python virtual environment and install PyQt6 and Pillow.
6. Install the application icon.
7. Create a launcher at `~/.local/bin/bazzcap` and a .desktop entry so BazzCap appears in your app menu.
8. Enable autostart on login (can be toggled later in Settings).
9. Add `~/.local/bin` to your PATH if needed.
10. Launch BazzCap in the system tray.

### macOS — Quick Install

```
git clone https://github.com/lak1z-azk/BazzCap.git
cd BazzCap
bash install_macos.sh
```

The installer will:
1. Check for Python 3 (installs via Homebrew if available).
2. Copy BazzCap files to `~/Library/Application Support/bazzcap/`.
3. Create a Python virtual environment and install PyQt6 and Pillow.
4. Create a launcher at `/usr/local/bin/bazzcap`.
5. Create a macOS `.app` bundle at `~/Applications/BazzCap.app` (works with Spotlight/Dock).
6. Set up a LaunchAgent for autostart on login.
7. Launch BazzCap in the menu bar.

> **Note:** macOS will ask for **Screen Recording** and **Accessibility** permissions on first use.
> Grant these in **System Settings → Privacy & Security**.

After installation, you can launch BazzCap by:
- Searching for "BazzCap" in Spotlight.
- Opening `~/Applications/BazzCap.app`.
- Running `bazzcap` in a terminal.

### Immutable Distributions (Bazzite, Silverblue, Kinoite)

The installer detects immutable systems and uses `rpm-ostree` automatically. Because rpm-ostree requires a reboot for packages to become available, the installer will:
1. Queue all missing packages via `rpm-ostree install`.
2. Notify you that a reboot is needed.
3. After rebooting, re-run `bash install.sh` to complete the installation.

### Manual Installation

If you prefer not to use the installer, follow these steps:

1. Install system dependencies (see the table above for your distro).

2. Clone the repository:
   ```
   git clone https://github.com/lak1z-azk/BazzCap.git
   cd BazzCap
   ```

3. Create a virtual environment and install Python dependencies:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. Run BazzCap:
   ```
   python bazzcap.py
   ```

5. (Optional) To install as a system app with a .desktop entry and autostart, use the installer:
   ```
   bash install.sh
   ```

### Uninstall

**Linux:**
```
bash install.sh --uninstall
```

**macOS:**
```
bash install_macos.sh --uninstall
```

This removes all installed files, desktop entries, autostart configuration, and any registered hotkeys (GNOME and KDE). Configuration files at `~/.config/bazzcap/` (Linux) or `~/Library/Application Support/bazzcap/` (macOS) are preserved in case you reinstall.

---

## Usage

### First Launch
After installation, BazzCap starts in the system tray. If the tray icon does not appear, open BazzCap from the application menu or run `bazzcap` in a terminal.

### Taking a Screenshot
1. Press the hotkey for the desired capture mode (default: Ctrl+Print for region capture).
2. A full-screen overlay appears with a crosshair cursor and magnifier.
3. Optionally, select an annotation tool from the toolbar at the top and draw on the screen.
4. Click and drag to select the region you want to capture.
5. The annotated screenshot is saved automatically to `~/Pictures/BazzCap/` and copied to the clipboard.
6. A desktop notification confirms the capture.

### Customizing Hotkeys
1. Open BazzCap settings from the tray menu or main window.
2. Navigate to the Hotkeys section.
3. Click on a hotkey field and press your desired key combination.
4. Changes are applied immediately and registered with your desktop environment.

### Start With System
BazzCap is configured to start automatically on login by default. You can toggle this in Settings by checking or unchecking "Start with system (autostart on login)". On Linux, this creates or removes an XDG autostart entry at `~/.config/autostart/bazzcap.desktop`. On macOS, this creates or removes a LaunchAgent at `~/Library/LaunchAgents/com.bazzcap.plist`.

### Changing Save Location
By default, captures are saved to `~/Pictures/BazzCap/`. This can be changed in the settings dialog.

### Main Window
The main BazzCap window provides quick-access buttons for all capture modes, a history list of recent captures, and buttons to open Settings or Hotkey configuration. Double-click any image in the history list to open it in the annotation editor.

### Configuration
All settings are stored in `~/.config/bazzcap/config.json` (Linux) or `~/Library/Application Support/bazzcap/config.json` (macOS). You can also change settings through the Settings dialog in the app. Available settings:
- Save directory and filename pattern
- Image format (PNG, JPEG, BMP, WebP)
- Auto-copy to clipboard after capture
- Show magnifier during region capture
- Annotation editor defaults (line width, font size, blur intensity)
- Minimize to tray on close
- Start with system (autostart on login)
- Hotkey bindings

---

## Project Structure

```
BazzCap/
  bazzcap/
    app.py                  Main window, system tray, settings dialog
    overlay.py              Region capture overlay with annotation tools
    editor.py               Image annotation editor (opened from history)
    capture.py              Screenshot backends (XDG Portal, grim, spectacle)
    clipboard.py            Clipboard integration (wl-copy, xclip, Qt)
    hotkeys.py              Global hotkey registration (GNOME, KDE)
    hotkey_settings.py      Hotkey configuration dialog
    config.py               Settings management
    history.py              Capture history
    _portal_helper.py       XDG Desktop Portal integration
    _trigger.py             Hotkey trigger via Unix socket
    resources/
      bazzcap.svg           Application icon
  bazzcap.py                Launcher script
  install.sh                Installer and uninstaller (Linux)
  install_macos.sh          Installer and uninstaller (macOS)
  requirements.txt          Python dependencies
```

---

## Troubleshooting

### BazzCap does not start
- Verify Python 3.10+ is installed: `python3 --version`
- **Linux:** Check if the virtual environment exists: `ls ~/.local/share/bazzcap/venv/`
- **macOS:** Check if the virtual environment exists: `ls ~/Library/Application\ Support/bazzcap/venv/`
- Try reinstalling: `bash install.sh` (Linux) or `bash install_macos.sh` (macOS)

### Hotkeys do not work
- Make sure BazzCap is running (check the system tray / menu bar).
- **GNOME:** Check that keybindings are registered: `gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings`
- **KDE:** Check System Settings > Shortcuts for BazzCap entries.
- **macOS:** Ensure Accessibility permission is granted in System Settings → Privacy & Security → Accessibility. BazzCap must be listed and checked.
- Some distributions override the Print key. You may need to unbind the default screenshot tool in your system settings first.

### Clipboard does not work
- **Linux (Wayland):** Install wl-clipboard: `sudo dnf install wl-clipboard`
- **Linux (X11):** Install xclip: `sudo dnf install xclip`
- **macOS:** Clipboard uses the built-in pbcopy/osascript — should work out of the box.

### Screenshots are blank or fail (macOS)
- Grant **Screen Recording** permission in System Settings → Privacy & Security → Screen Recording. BazzCap (or Terminal / the Python binary) must be listed and checked.
- You may need to restart BazzCap after granting permissions.

### "bazzcap: command not found"
- **Linux:** Add `~/.local/bin` to your PATH. Add this line to `~/.bashrc`:
  ```
  export PATH="$HOME/.local/bin:$PATH"
  ```
  Then restart your terminal or run `source ~/.bashrc`.
- **macOS:** The installer places the launcher at `/usr/local/bin/bazzcap`. If using `~/bin` instead, add it to your PATH in `~/.zshrc`.

---

## Contributing

BazzCap is an open-source project and contributions are welcome! Whether it's fixing a bug, adding a feature, improving documentation, or just reporting an issue -- every contribution helps.

- **Bug reports & feature requests**: [Open an issue](https://github.com/lak1z-azk/BazzCap/issues)
- **Pull requests**: Fork the repo, make your changes, and submit a PR. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
- **Discussions**: Have a question or idea? Start a conversation in [Issues](https://github.com/lak1z-azk/BazzCap/issues).

All skill levels are welcome. If you use BazzCap and want to help make it better, jump in!

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
