# BazzCap

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![GUI: PyQt6](https://img.shields.io/badge/GUI-PyQt6-41cd52.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-orange.svg)]()
[![Platform: macOS](https://img.shields.io/badge/Platform-macOS-lightgrey.svg)]()

BazzCap is a desktop screenshot tool for Linux and macOS built with Python and PyQt6. It focuses on fast captures, built-in annotation, a clean dark UI, and a practical history workflow so you can keep working instead of juggling separate apps.

It supports fullscreen, region, and window capture, lives in the tray/menu bar, copies captures to the clipboard automatically, and lets you re-open previous screenshots in a full editor without overwriting the original file.

## Highlights

- Fullscreen, region, and window capture
- Built-in annotation overlay before saving
- Dedicated image editor for post-editing captures
- Dark minimal main UI and dark editor theme
- History actions: edit copy, open, duplicate, reveal, delete, remove missing
- Global hotkeys on Linux desktop environments and fallback macOS support
- Optional autostart on login
- Single-instance protection
- Automatic clipboard copy and desktop notifications

## Capture Workflow

BazzCap is designed around a simple flow:

1. Trigger a capture from a hotkey, tray icon, or main window.
2. Annotate before saving if you want to add arrows, text, blur, highlights, or steps.
3. Save automatically to your configured folder and copy the result to the clipboard.
4. Re-open any previous capture from the history panel and continue editing as a new copy.

Region capture uses the full-screen overlay, while fullscreen and window capture remain one-click flows. The duplicate-save bug for selected captures has been fixed, so only the intended screenshot is kept.

## Annotation Tools

The capture overlay and image editor support the same practical markup toolbox:

- Arrow
- Rectangle
- Filled rectangle
- Ellipse
- Line
- Freehand
- Text
- Blur
- Highlight
- Numbered steps

You can move annotations after placing them, delete them, crop in the editor, copy the result to the clipboard, and save new edited versions without touching the original screenshot.

## History and Editing

The right side of the main window is a working history panel, not just a log.

From recent captures you can:

- `Edit` to open an editable copy
- `Open` with the system default app
- `Duplicate` the file instantly
- `Delete` the file from disk
- `Remove Missing` to clean stale history entries
- Right-click for quick actions including `Show in Folder`

Double-clicking a capture opens an editable copy in the built-in editor. Edited screenshots are saved as new files and added back into history automatically.

## Hotkeys

Default Linux hotkeys:

| Action | Default |
| --- | --- |
| Fullscreen Capture | `Print` |
| Region Capture | `Ctrl+Print` |
| Window Capture | `Alt+Print` |

Default macOS hotkeys:

| Action | Default |
| --- | --- |
| Fullscreen Capture | `Cmd+Shift+1` |
| Region Capture | `Cmd+Shift+2` |
| Window Capture | `Cmd+Shift+6` |

Hotkeys can be customized from the settings dialog.

## Releases

GitHub Releases are the easiest way to grab packaged builds:

- Linux: `AppImage`
- macOS: zipped `.app` bundle

Release page:

```text
https://github.com/ManCaveWasteland/BazzCap/releases
```

If you prefer source-based installation, use the installer scripts below.

## Installation

### Linux quick install

```bash
git clone https://github.com/ManCaveWasteland/BazzCap.git
cd BazzCap
bash install.sh
```

The Linux installer will:

- install missing system dependencies
- create a local app directory and virtual environment
- install Python dependencies
- register a desktop entry
- set up a launcher
- optionally enable autostart on login

### macOS quick install

```bash
git clone https://github.com/ManCaveWasteland/BazzCap.git
cd BazzCap
bash install_macos.sh
```

The macOS installer will:

- copy the app into `~/Library/Application Support/bazzcap/`
- create a virtual environment
- install dependencies
- create a launcher command
- create a `BazzCap.app` bundle
- register autostart with LaunchAgent

### Manual run from source

```bash
git clone https://github.com/ManCaveWasteland/BazzCap.git
cd BazzCap
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 bazzcap.py
```

## Requirements

### Linux

- Python 3.10+
- Wayland or X11
- GNOME or KDE Plasma recommended for the best hotkey integration
- Common tools used by the app or installer: `xdotool`, `wl-clipboard`, `grim` or `spectacle`, `libnotify`

### macOS

- macOS 11+
- Python 3.10+
- Screen Recording permission
- Accessibility permission for hotkeys

## Settings

The settings dialog lets you configure:

- save directory
- filename pattern
- autostart on login
- default annotation line width
- default font size
- blur radius

## Project Structure

```text
BazzCap/
├── bazzcap/
│   ├── app.py
│   ├── capture.py
│   ├── overlay.py
│   ├── editor.py
│   ├── history.py
│   ├── hotkeys.py
│   └── config.py
├── bazzcap.py
├── install.sh
├── install_macos.sh
└── requirements.txt
```

## Uninstall

Linux:

```bash
bash install.sh --uninstall
```

macOS:

```bash
bash install_macos.sh --uninstall
```

## Contributing

Issues, feature ideas, and pull requests are welcome. If you are reporting a bug, include your OS, desktop environment, display server, and the exact capture mode or editor action that failed.

## License

Released under the [MIT License](LICENSE).
