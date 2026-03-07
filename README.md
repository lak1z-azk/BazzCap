# BazzCap

A screenshot tool for Linux, built with Python and PyQt6. Designed for Bazzite, Fedora, and other Linux distributions running GNOME or KDE on Wayland (X11 also supported).

BazzCap lives in the system tray and provides global hotkeys for region capture, fullscreen capture, and window capture -- with annotation tools built directly into the capture overlay.
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

  <img width="751" height="65" alt="image" src="https://github.com/user-attachments/assets/364cc2e6-b79f-49d4-b0b2-b2f05cdcaba9" />


All annotations can be dragged to reposition them after placement. Hover over an annotation and press DEL to remove it. After selecting a region, the annotated screenshot is saved automatically and copied to the clipboard.

### History Editor
Double-clicking a capture in the history list opens a full image editor where you can draw additional annotations (rectangle, ellipse, line, arrow, freehand, text, blur, highlight, numbered steps), crop the image, copy to clipboard, or save to a new file.

### Hotkeys
Global keyboard shortcuts are registered with your desktop environment (GNOME or KDE) so they work even when BazzCap is not focused.

| Action             | Default Hotkey |
|--------------------|----------------|
| Fullscreen Capture | Print          |
| Region Capture     | Ctrl+Print     |
| Window Capture     | Alt+Print      |

Hotkeys are fully customizable from the settings dialog inside BazzCap.

<img width="505" height="369" alt="image" src="https://github.com/user-attachments/assets/08bbeb48-d936-4cf0-9dd6-b4d499b244b3" />


### System Tray
BazzCap runs in the system tray. Right-click the tray icon to quickly start a capture, open settings, configure hotkeys, or quit. Double-click the tray icon to open the main window. Middle-click to start a region capture instantly. The main window can be minimized to tray on close.

### Desktop Integration
- **GNOME**: Hotkeys are registered as custom keybindings via gsettings.
- **KDE Plasma**: Hotkeys are registered via .desktop shortcut files and kglobalaccel D-Bus.
- **Autostart**: Optional autostart on login via XDG autostart.
- **Clipboard**: Captures are automatically copied to the clipboard using wl-copy (Wayland), xclip, or Qt clipboard as fallback.
- **Notifications**: Desktop notifications on capture completion via notify-send.

---

## Requirements

### System
- Linux (tested on Bazzite / Fedora, should work on any distribution)
- Python 3.10 or newer
- GNOME or KDE Plasma desktop environment (for global hotkeys)
- Wayland or X11 display server

### Required System Packages
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

### Python Dependencies
These are installed automatically inside a virtual environment by the installer:
- PyQt6 >= 6.5.0
- Pillow >= 9.0.0

---

## Installation

### Quick Install (Recommended)

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

After installation, you can launch BazzCap by:
- Searching for "BazzCap" in your application menu.
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

```
bash install.sh --uninstall
```

This removes all installed files, desktop entries, autostart configuration, and any registered hotkeys (GNOME and KDE). Configuration files at `~/.config/bazzcap/` are preserved in case you reinstall.

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
BazzCap is configured to start automatically on login by default. You can toggle this in Settings by checking or unchecking "Start with system (autostart on login)". This creates or removes an XDG autostart entry at `~/.config/autostart/bazzcap.desktop`.

### Changing Save Location
By default, captures are saved to `~/Pictures/BazzCap/`. This can be changed in the settings dialog.

### Main Window
The main BazzCap window provides quick-access buttons for all capture modes, a history list of recent captures, and buttons to open Settings or Hotkey configuration. Double-click any image in the history list to open it in the annotation editor.

### Configuration
All settings are stored in `~/.config/bazzcap/config.json`. You can also change settings through the Settings dialog in the app. Available settings:
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
  install.sh                Installer and uninstaller
  requirements.txt          Python dependencies
```

---

## Troubleshooting

### BazzCap does not start
- Verify Python 3.10+ is installed: `python3 --version`
- Check if the virtual environment exists: `ls ~/.local/share/bazzcap/venv/`
- Try reinstalling: `bash install.sh`

### Hotkeys do not work
- Make sure BazzCap is running (check the system tray).
- On GNOME, check that keybindings are registered: `gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings`
- On KDE, check System Settings > Shortcuts for BazzCap entries.
- Some distributions override the Print key. You may need to unbind the default screenshot tool in your system settings first.

### Clipboard does not work
- Install wl-clipboard: `sudo dnf install wl-clipboard`
- On X11, install xclip: `sudo dnf install xclip`

### "bazzcap: command not found"
- Add `~/.local/bin` to your PATH. Add this line to `~/.bashrc`:
  ```
  export PATH="$HOME/.local/bin:$PATH"
  ```
- Then restart your terminal or run `source ~/.bashrc`.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
