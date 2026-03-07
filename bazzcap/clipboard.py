"""Clipboard utilities for BazzCap — works on Wayland and X11.

Priority order:
  1. wl-copy (Wayland native)
  2. xclip (X11 / XWayland)
  3. PyQt6 QClipboard (universal fallback — always available)
"""

import subprocess
import shutil
import os


def _is_wayland():
    """Check if we're running under Wayland."""
    return os.environ.get("WAYLAND_DISPLAY") or \
           os.environ.get("XDG_SESSION_TYPE") == "wayland"


def _has(cmd):
    """Check if a command is available."""
    return shutil.which(cmd) is not None


def _qt_copy_image(image_path: str) -> bool:
    """Copy image to clipboard using Qt (works everywhere PyQt6 runs)."""
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QPixmap, QImage

        app = QApplication.instance()
        if app is None:
            return False

        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return False

        clipboard = app.clipboard()
        clipboard.setPixmap(pixmap)
        return True
    except Exception:
        return False


def _qt_copy_text(text: str) -> bool:
    """Copy text to clipboard using Qt."""
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return False

        clipboard = app.clipboard()
        clipboard.setText(text)
        return True
    except Exception:
        return False


def copy_image_to_clipboard(image_path: str) -> bool:
    """Copy an image file to the system clipboard.

    Tries wl-copy (Wayland), xclip (X11), then Qt clipboard (universal).
    Returns True on success.
    """
    if not os.path.isfile(image_path):
        return False

    mime = "image/png"
    if image_path.lower().endswith(".jpg") or image_path.lower().endswith(".jpeg"):
        mime = "image/jpeg"

    # Wayland: wl-copy
    if _is_wayland() and _has("wl-copy"):
        try:
            with open(image_path, "rb") as f:
                subprocess.run(
                    ["wl-copy", "--type", mime],
                    stdin=f, timeout=5, check=True,
                )
            return True
        except (subprocess.SubprocessError, IOError):
            pass

    # X11 / XWayland: xclip
    if _has("xclip"):
        try:
            with open(image_path, "rb") as f:
                subprocess.run(
                    ["xclip", "-selection", "clipboard", "-t", mime, "-i"],
                    stdin=f, timeout=5, check=True,
                )
            return True
        except (subprocess.SubprocessError, IOError):
            pass

    # Universal fallback: Qt clipboard
    if _qt_copy_image(image_path):
        return True

    # Last resort: xsel (text path only)
    if _has("xsel"):
        try:
            subprocess.run(
                ["xsel", "--clipboard", "--input"],
                input=image_path.encode(), timeout=5, check=True,
            )
            return True
        except (subprocess.SubprocessError, IOError):
            pass

    return False


def copy_text_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard."""
    if _is_wayland() and _has("wl-copy"):
        try:
            subprocess.run(
                ["wl-copy", text], timeout=5, check=True,
            )
            return True
        except subprocess.SubprocessError:
            pass

    if _has("xclip"):
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode(), timeout=5, check=True,
            )
            return True
        except subprocess.SubprocessError:
            pass

    # Qt fallback
    if _qt_copy_text(text):
        return True

    return False
