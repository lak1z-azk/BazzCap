import os
import shutil
import subprocess
import sys

IS_MACOS = sys.platform == "darwin"


def _is_wayland():
    return os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland"


def _qt_copy_image(image_path: str) -> bool:
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QPixmap

        app = QApplication.instance()
        if app is None:
            return False
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return False
        app.clipboard().setPixmap(pixmap)
        return True
    except Exception:
        return False


def _qt_copy_text(text: str) -> bool:
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            return False
        app.clipboard().setText(text)
        return True
    except Exception:
        return False


def copy_image_to_clipboard(image_path: str) -> bool:
    if not os.path.isfile(image_path):
        return False

    if IS_MACOS:
        # Path is bound as an argv item, not interpolated into the script text.
        script = (
            "on run argv\n"
            "  set the clipboard to (read (POSIX file (item 1 of argv)) as «class PNGf»)\n"
            "end run"
        )
        try:
            subprocess.run(
                ["osascript", "-e", script, image_path],
                capture_output=True, timeout=5, check=True,
            )
            return True
        except (subprocess.SubprocessError, OSError):
            pass
        return _qt_copy_image(image_path)

    mime = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"

    if _is_wayland() and shutil.which("wl-copy"):
        try:
            with open(image_path, "rb") as f:
                subprocess.run(
                    ["wl-copy", "--type", mime],
                    stdin=f, timeout=5, check=True,
                )
            return True
        except (subprocess.SubprocessError, IOError):
            pass

    if shutil.which("xclip"):
        try:
            with open(image_path, "rb") as f:
                subprocess.run(
                    ["xclip", "-selection", "clipboard", "-t", mime, "-i"],
                    stdin=f, timeout=5, check=True,
                )
            return True
        except (subprocess.SubprocessError, IOError):
            pass

    return _qt_copy_image(image_path)


def copy_text_to_clipboard(text: str) -> bool:
    if IS_MACOS:
        try:
            subprocess.run(["pbcopy"], input=text.encode(), timeout=5, check=True)
            return True
        except (subprocess.SubprocessError, OSError):
            pass
        return _qt_copy_text(text)

    if _is_wayland() and shutil.which("wl-copy"):
        try:
            subprocess.run(["wl-copy", text], timeout=5, check=True)
            return True
        except subprocess.SubprocessError:
            pass

    if shutil.which("xclip"):
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode(), timeout=5, check=True,
            )
            return True
        except subprocess.SubprocessError:
            pass

    return _qt_copy_text(text)
