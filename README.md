# BazzCap

> A fast, open-source screenshot and annotation tool for Linux and macOS — built with Python and PyQt6.

[![Latest Release](https://img.shields.io/github/v/release/lak1z-azk/BazzCap?label=release)](https://github.com/lak1z-azk/BazzCap/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![GUI: PyQt6](https://img.shields.io/badge/GUI-PyQt6-41cd52.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-orange.svg)]()
[![Platform: macOS](https://img.shields.io/badge/Platform-macOS-lightgrey.svg)]()

BazzCap is a desktop screenshot tool for **Linux and macOS** focused on fast screen capture, built-in annotation, a clean dark UI, and a practical screenshot history workflow. It is a lightweight open-source alternative for users who want capture and editing in one application instead of juggling separate tools.

Capture a fullscreen, region, or window screenshot, annotate it with arrows, text, blur, highlights, shapes, or numbered steps, and automatically copy the result to your clipboard. Previous screenshots can be reopened in the built-in editor without overwriting the original file.

**Great for:** bug reports, documentation, tutorials, support tickets, development workflows, and quickly sharing annotated screenshots.

## Download

The easiest way to use BazzCap is through [GitHub Releases](https://github.com/lak1z-azk/BazzCap/releases/latest).

- **Linux:** AppImage
- **macOS:** packaged app builds when available
- **Source:** Python 3.10+

Linux AppImage:

```bash
chmod +x BazzCap-*.AppImage
./BazzCap-*.AppImage
```

## Features

- Fullscreen, region, and window screenshot capture
- Built-in screenshot annotation before saving
- Dedicated image editor for post-editing captures
- Arrow, rectangle, ellipse, line, freehand, text, blur, highlight, and numbered-step tools
- Crop and move annotations after placing them
- Automatic clipboard copy
- Screenshot history with edit, open, duplicate, reveal, and delete actions
- Global configurable hotkeys
- System tray / menu bar integration
- Optional autostart on login
- Single-instance protection
- Desktop notifications
- Dark UI and editor theme
- Linux Wayland and X11 support
- macOS support

## Capture Workflow

1. Trigger a capture from a hotkey, tray icon, or the main window.
2. Select fullscreen, region, or window capture.
3. Add annotations such as arrows, text, blur, highlights, shapes, or numbered steps.
4. Save automatically to your configured folder and copy the result to the clipboard.
5. Re-open previous captures from history and continue editing them as new copies.

Region capture uses a full-screen overlay, while fullscreen and window capture remain quick one-click flows.

## Annotation Tools

The capture overlay and image editor provide the same practical markup toolbox:

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

The right side of the main window is a working screenshot history panel rather than only a log.

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

## Installation from Source

### Linux

```bash
git clone https://github.com/lak1z-azk/BazzCap.git
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

### macOS

```bash
git clone https://github.com/lak1z-azk/BazzCap.git
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

### Manual Python setup

```bash
git clone https://github.com/lak1z-azk/BazzCap.git
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

BazzCap's packaged AppImage includes the dependencies required for its XDG Desktop Portal screenshot path, making it suitable for image-based Linux distributions such as Bazzite, Fedora Silverblue, and Kinoite.

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

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidance.

If you are reporting a bug, please include your operating system, desktop environment, display server, and the exact capture mode or editor action that failed.

If BazzCap is useful to you, consider starring the repository — it helps other Linux and macOS users discover the project.

## License

Released under the [MIT License](LICENSE).
