# BazzCap

A screenshot and screen recording tool for Linux, built with Python and PyQt6. Designed for Bazzite, Fedora, and other Linux distributions running GNOME or KDE on Wayland (X11 also supported).

BazzCap lives in the system tray and provides global hotkeys for region capture, fullscreen capture, window capture, video recording, and GIF recording -- all with a built-in annotation editor.

---

## Features

### Capture Modes
- **Region Capture** -- Select a rectangular area of the screen with a crosshair overlay and magnifier for precision.
- **Fullscreen Capture** -- Instantly capture the entire screen (multi-monitor aware).
- **Window Capture** -- Capture the currently focused window.
- **Video Recording** -- Record a selected region or the full screen to MP4 using FFmpeg and PipeWire.
- **GIF Recording** -- Record a region as an animated GIF.

### Annotation Tools
When capturing a region, an overlay appears across the full screen allowing you to annotate before selecting the final area. The following tools are available in the overlay toolbar:

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

All annotations can be dragged to reposition them after placement. Hover over an annotation and press DEL to remove it.

### Editor
After capturing, an image editor opens where you can:
- Crop and resize the image.
- Draw additional annotations.
- Apply filters.
- Save in PNG, JPEG, or other formats.
- Copy directly to clipboard.

### Hotkeys
Global keyboard shortcuts are registered with your desktop environment (GNOME or KDE) so they work even when BazzCap is not focused.

| Action             | Default Hotkey     |
|--------------------|--------------------|
| Fullscreen Capture | Print              |
| Region Capture     | Ctrl+Print         |
| Window Capture     | Alt+Print          |
| Video Recording    | Ctrl+Shift+Print   |
| GIF Recording      | Ctrl+Alt+Print     |

Hotkeys are fully customizable from the settings dialog inside BazzCap.

### System Tray
BazzCap runs in the system tray. Right-click the tray icon to access capture actions, open settings, view capture history, or quit the application. The main window can be minimized to tray and restored at any time.

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
These must be installed on your system before running the installer:

| Package        | Purpose                          | Install Command (Fedora)       |
|----------------|----------------------------------|--------------------------------|
| python3        | Application runtime              | Pre-installed on most distros  |
| python3-venv   | Virtual environment support      | `sudo dnf install python3-libs`|

### Recommended Packages
The installer will check for these and warn if any are missing:

| Package        | Purpose                          | Install Command (Fedora)       |
|----------------|----------------------------------|--------------------------------|
| xdotool        | Cursor position detection        | `sudo dnf install xdotool`     |
| ffmpeg         | Video recording and GIF creation | `sudo dnf install ffmpeg`      |
| wl-clipboard   | Clipboard support on Wayland     | `sudo dnf install wl-clipboard`|
| grim           | Screenshot backend (GNOME)       | `sudo dnf install grim`        |
| spectacle      | Screenshot backend (KDE)         | `sudo dnf install spectacle`   |
| libnotify      | Desktop notifications            | `sudo dnf install libnotify`   |

For Debian/Ubuntu, replace `dnf` with `apt` and use `python3-venv` instead of `python3-libs`.

### Python Dependencies
These are installed automatically inside a virtual environment by the installer:
- PyQt6 >= 6.5.0
- Pillow >= 9.0.0

---

## Installation

### Quick Install

1. Clone the repository:
   ```
   git clone https://github.com/lak1z-azk/BazzCap.git
   cd BazzCap
   ```

2. Run the installer:
   ```
   bash install.sh
   ```

The installer performs the following steps:
1. Verifies Python 3 and the venv module are available.
2. Checks for recommended system tools (xdotool, ffmpeg, wl-clipboard, grim/spectacle).
3. Copies the application files to `~/.local/share/bazzcap/`.
4. Creates a Python virtual environment and installs dependencies (PyQt6, Pillow).
5. Installs the application icon.
6. Creates a launcher script at `~/.local/bin/bazzcap` and a .desktop entry.
7. Optionally sets up autostart on login.
8. Launches BazzCap in the system tray.

After installation, you can launch BazzCap by:
- Running `bazzcap` in a terminal.
- Searching for "BazzCap" in your application menu.

### Immutable Distributions (Bazzite, Silverblue, Kinoite)

On immutable Fedora-based distributions, use `rpm-ostree` to install system packages:
```
rpm-ostree install xdotool ffmpeg wl-clipboard grim libnotify
```
A reboot is required after installing packages with rpm-ostree. Then proceed with the regular install steps above.

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
2. For region capture, a full-screen overlay appears with a crosshair cursor and magnifier.
3. Optionally, select an annotation tool from the toolbar at the top and draw on the screen.
4. Click and drag to select the region you want to capture.
5. The captured image opens in the editor where you can make further edits.
6. Save the image or close the editor -- the image is automatically copied to the clipboard (if wl-copy is installed).

### Recording the Screen
1. Press the recording hotkey (default: Ctrl+Shift+Print for video, Ctrl+Alt+Print for GIF).
2. Select the region to record.
3. Recording starts immediately. Press the hotkey again or use the tray menu to stop recording.
4. The recording is saved to `~/Pictures/BazzCap/`.

### Customizing Hotkeys
1. Open BazzCap settings from the tray menu or main window.
2. Navigate to the Hotkeys section.
3. Click on a hotkey field and press your desired key combination.
4. Changes are applied immediately and registered with your desktop environment.

### Changing Save Location
By default, captures are saved to `~/Pictures/BazzCap/`. This can be changed in the settings dialog.

### Configuration
All settings are stored in `~/.config/bazzcap/config.json`. You can edit this file directly if needed. Settings include:
- Save directory and filename pattern
- Image format (PNG, JPEG) and quality
- Recording format, FPS, and GIF settings
- Editor defaults (color, line width, font size, blur radius)
- Hotkey bindings
- Tray behavior

---

## Project Structure

```
BazzCap/
  bazzcap/                  # Main application package
    app.py                  # Main window, system tray, application entry
    overlay.py              # Region capture overlay with annotation tools
    editor.py               # Post-capture image editor
    capture.py              # Screenshot backends (XDG Portal, grim, spectacle, etc.)
    recorder.py             # Screen recording backends (PipeWire, wf-recorder, FFmpeg)
    clipboard.py            # Clipboard integration (wl-copy, xclip, Qt)
    hotkeys.py              # Global hotkey registration (GNOME, KDE)
    hotkey_settings.py      # Hotkey settings UI
    config.py               # Configuration management
    history.py              # Capture history tracking
    _portal_helper.py       # XDG Desktop Portal integration
    _trigger.py             # External trigger via Unix socket
    resources/
      bazzcap.svg           # Application icon
  bazzcap.py                # Launcher script
  install.sh                # Installer / uninstaller
  requirements.txt          # Python dependencies
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

### Screen recording produces no output
- Install ffmpeg: `sudo dnf install ffmpeg`
- On Wayland, PipeWire must be running (it is by default on Fedora/Bazzite).
- Check that the save directory exists and is writable.

### "bazzcap: command not found"
- Add `~/.local/bin` to your PATH. Add this line to `~/.bashrc`:
  ```
  export PATH="$HOME/.local/bin:$PATH"
  ```
- Then restart your terminal or run `source ~/.bashrc`.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
