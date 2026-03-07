"""Screenshot capture module for BazzCap.

Supports Wayland (KDE Plasma, GNOME) and X11 via multiple backends:
  1. XDG Desktop Portal (universal Wayland — both KDE & GNOME)
  2. spectacle (KDE)
  3. gnome-screenshot (GNOME)
  4. grim + slurp (wlroots compositors)
  5. scrot / maim / import (X11 fallback)
"""

import subprocess
import shutil
import os
import tempfile
import time
from enum import Enum, auto
from pathlib import Path


class CaptureMode(Enum):
    FULLSCREEN = auto()
    REGION = auto()
    WINDOW = auto()


def _has(cmd):
    return shutil.which(cmd) is not None


def _run(cmd, timeout=30):
    """Run a command, return (success, stdout)."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode == 0, r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False, ""


def _portal_screenshot(interactive: bool = True) -> str | None:
    """Take a screenshot via XDG Desktop Portal using dbus-send + monitor.

    This is the most universal method for Wayland (works on KDE and GNOME).
    Returns the file path on success, None on failure.
    """
    # Use a Python helper with dbus-python if available
    helper = os.path.join(os.path.dirname(__file__), "_portal_helper.py")
    if os.path.exists(helper):
        try:
            r = subprocess.run(
                ["python3", helper, "screenshot",
                 "--interactive" if interactive else "--fullscreen"],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0 and r.stdout.strip():
                path = r.stdout.strip()
                if os.path.isfile(path):
                    return path
        except (subprocess.SubprocessError, OSError):
            pass

    # Fallback: use gdbus call (may not capture the response signal easily,
    # but on some systems it works synchronously)
    try:
        token = f"bazzcap_{int(time.time())}"
        interactive_str = "true" if interactive else "false"
        r = subprocess.run(
            [
                "gdbus", "call", "--session",
                "--dest", "org.freedesktop.portal.Desktop",
                "--object-path", "/org/freedesktop/portal/desktop",
                "--method", "org.freedesktop.portal.Screenshot.Screenshot",
                "", f"{{'interactive': <{interactive_str}>, 'handle_token': <'{token}'>}}"
            ],
            capture_output=True, text=True, timeout=30,
        )
        # The portal saves to a temp file and returns URI in the response signal.
        # With gdbus call we only get the request handle, not the response.
        # The helper script approach is more reliable.
    except (subprocess.SubprocessError, OSError):
        pass

    return None


def capture_fullscreen(output_path: str) -> bool:
    """Capture the entire screen. Returns True on success."""
    # Method 1: XDG Portal (non-interactive = fullscreen)
    portal_path = _portal_screenshot(interactive=False)
    if portal_path:
        try:
            shutil.copy2(portal_path, output_path)
            return True
        except IOError:
            pass

    # Method 2: spectacle (KDE)
    if _has("spectacle"):
        ok, _ = _run(["spectacle", "-b", "-n", "-f", "-o", output_path])
        if ok and os.path.isfile(output_path):
            return True

    # Method 3: gnome-screenshot
    if _has("gnome-screenshot"):
        ok, _ = _run(["gnome-screenshot", "-f", output_path])
        if ok and os.path.isfile(output_path):
            return True

    # Method 4: grim (wlroots Wayland)
    if _has("grim"):
        ok, _ = _run(["grim", output_path])
        if ok and os.path.isfile(output_path):
            return True

    # Method 5: scrot (X11)
    if _has("scrot"):
        ok, _ = _run(["scrot", output_path])
        if ok and os.path.isfile(output_path):
            return True

    # Method 6: maim (X11)
    if _has("maim"):
        ok, _ = _run(["maim", output_path])
        if ok and os.path.isfile(output_path):
            return True

    # Method 7: import from ImageMagick (X11)
    if _has("import"):
        ok, _ = _run(["import", "-window", "root", output_path])
        if ok and os.path.isfile(output_path):
            return True

    return False


def capture_region(output_path: str) -> bool:
    """Capture a user-selected region. Returns True on success."""
    # Method 1: XDG Portal (interactive mode — compositor shows region selector)
    portal_path = _portal_screenshot(interactive=True)
    if portal_path:
        try:
            shutil.copy2(portal_path, output_path)
            return True
        except IOError:
            pass

    # Method 2: spectacle region mode (KDE)
    if _has("spectacle"):
        ok, _ = _run(["spectacle", "-b", "-n", "-r", "-o", output_path])
        if ok and os.path.isfile(output_path):
            return True

    # Method 3: gnome-screenshot area mode
    if _has("gnome-screenshot"):
        ok, _ = _run(["gnome-screenshot", "-a", "-f", output_path])
        if ok and os.path.isfile(output_path):
            return True

    # Method 4: grim + slurp (wlroots)
    if _has("grim") and _has("slurp"):
        try:
            slurp = subprocess.run(
                ["slurp"], capture_output=True, text=True, timeout=30,
            )
            if slurp.returncode == 0 and slurp.stdout.strip():
                geometry = slurp.stdout.strip()
                ok, _ = _run(["grim", "-g", geometry, output_path])
                if ok and os.path.isfile(output_path):
                    return True
        except (subprocess.SubprocessError, OSError):
            pass

    # Method 5: scrot select (X11)
    if _has("scrot"):
        ok, _ = _run(["scrot", "-s", output_path])
        if ok and os.path.isfile(output_path):
            return True

    # Method 6: maim select (X11)
    if _has("maim") and _has("slop"):
        try:
            slop = subprocess.run(
                ["slop", "-f", "%g"], capture_output=True, text=True, timeout=30,
            )
            if slop.returncode == 0 and slop.stdout.strip():
                geometry = slop.stdout.strip()
                ok, _ = _run(["maim", "-g", geometry, output_path])
                if ok and os.path.isfile(output_path):
                    return True
        except (subprocess.SubprocessError, OSError):
            pass

    return False


def capture_window(output_path: str) -> bool:
    """Capture the active/selected window. Returns True on success."""
    # Method 1: XDG Portal interactive (user picks a window)
    portal_path = _portal_screenshot(interactive=True)
    if portal_path:
        try:
            shutil.copy2(portal_path, output_path)
            return True
        except IOError:
            pass

    # Method 2: spectacle active window (KDE)
    if _has("spectacle"):
        ok, _ = _run(["spectacle", "-b", "-n", "-a", "-o", output_path])
        if ok and os.path.isfile(output_path):
            return True

    # Method 3: gnome-screenshot window
    if _has("gnome-screenshot"):
        ok, _ = _run(["gnome-screenshot", "-w", "-f", output_path])
        if ok and os.path.isfile(output_path):
            return True

    # Method 4: scrot focused window (X11)
    if _has("scrot"):
        ok, _ = _run(["scrot", "-u", output_path])
        if ok and os.path.isfile(output_path):
            return True

    # Method 5: maim focused window (X11)
    if _has("maim") and _has("xdotool"):
        try:
            xdo = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True, text=True, timeout=5,
            )
            if xdo.returncode == 0:
                wid = xdo.stdout.strip()
                ok, _ = _run(["maim", "-i", wid, output_path])
                if ok and os.path.isfile(output_path):
                    return True
        except (subprocess.SubprocessError, OSError):
            pass

    return False


def capture(mode: CaptureMode, output_path: str) -> bool:
    """Unified capture function."""
    if mode == CaptureMode.FULLSCREEN:
        return capture_fullscreen(output_path)
    elif mode == CaptureMode.REGION:
        return capture_region(output_path)
    elif mode == CaptureMode.WINDOW:
        return capture_window(output_path)
    return False


def detect_available_backends() -> list[str]:
    """Return list of available capture backends for diagnostics."""
    backends = []
    if _has("gdbus"):
        backends.append("XDG Portal (gdbus)")
    if _has("spectacle"):
        backends.append("Spectacle (KDE)")
    if _has("gnome-screenshot"):
        backends.append("GNOME Screenshot")
    if _has("grim"):
        backends.append("grim" + (" + slurp" if _has("slurp") else ""))
    if _has("scrot"):
        backends.append("scrot")
    if _has("maim"):
        backends.append("maim" + (" + slop" if _has("slop") else ""))
    if _has("import"):
        backends.append("ImageMagick import")
    return backends
