import os
import shutil
import subprocess
import sys
import time
from enum import Enum, auto

from bazzcap.runtime import external_command_env, is_flatpak, iter_python_commands, packaged_script_path

IS_MACOS = sys.platform == "darwin"


class CaptureMode(Enum):
    FULLSCREEN = auto()
    REGION = auto()
    WINDOW = auto()


def _has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _run(cmd: list[str], timeout: int = 30) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=external_command_env(),
        )
        return result.returncode == 0, result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False, ""



def _portal_screenshot(interactive: bool = True) -> str | None:
    helper = packaged_script_path("_portal_helper.py")
    if os.path.isfile(helper):
        helper_args = [
            helper,
            "screenshot",
            "--interactive" if interactive else "--fullscreen",
        ]
        for python_cmd in iter_python_commands(prefer_host=is_flatpak()):
            try:
                result = subprocess.run(
                    python_cmd + helper_args,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    env=external_command_env(),
                )
                if result.returncode == 0 and result.stdout.strip():
                    path = result.stdout.strip()
                    if os.path.isfile(path):
                        return path
            except (subprocess.SubprocessError, OSError):
                continue

    try:
        token = f"bazzcap_{int(time.time())}"
        interactive_str = "true" if interactive else "false"
        subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.freedesktop.portal.Desktop",
                "--object-path",
                "/org/freedesktop/portal/desktop",
                "--method",
                "org.freedesktop.portal.Screenshot.Screenshot",
                "",
                f"{{'interactive': <{interactive_str}>, 'handle_token': <'{token}'>}}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=external_command_env(),
        )
    except (subprocess.SubprocessError, OSError):
        pass

    return None


def capture_fullscreen(output_path: str) -> bool:
    if IS_MACOS:
        ok, _ = _run(["screencapture", "-x", output_path])
        return ok and os.path.isfile(output_path)

    # Try grim first — silent Wayland capture, no screen flash
    if _has("grim"):
        ok, _ = _run(["grim", output_path])
        if ok and os.path.isfile(output_path):
            return True
    elif is_flatpak():
        ok, _ = _run(["flatpak-spawn", "--host", "grim", output_path])
        if ok and os.path.isfile(output_path):
            return True

    portal_path = _portal_screenshot(interactive=False)
    if portal_path:
        try:
            shutil.copy2(portal_path, output_path)
            return True
        except IOError:
            pass
        finally:
            try:
                os.unlink(portal_path)
            except OSError:
                pass

    if _has("spectacle"):
        ok, _ = _run(["spectacle", "-b", "-n", "-f", "-o", output_path])
        if ok and os.path.isfile(output_path):
            return True

    if _has("scrot"):
        ok, _ = _run(["scrot", output_path])
        if ok and os.path.isfile(output_path):
            return True

    if _has("maim"):
        ok, _ = _run(["maim", output_path])
        if ok and os.path.isfile(output_path):
            return True

    if _has("import"):
        ok, _ = _run(["import", "-window", "root", output_path])
        if ok and os.path.isfile(output_path):
            return True

    return False


def capture_region(output_path: str) -> bool:
    if IS_MACOS:
        ok, _ = _run(["screencapture", "-i", "-x", output_path])
        return ok and os.path.isfile(output_path)

    portal_path = _portal_screenshot(interactive=True)
    if portal_path:
        try:
            shutil.copy2(portal_path, output_path)
            return True
        except IOError:
            pass
        finally:
            try:
                os.unlink(portal_path)
            except OSError:
                pass

    if _has("spectacle"):
        ok, _ = _run(["spectacle", "-b", "-n", "-r", "-o", output_path])
        if ok and os.path.isfile(output_path):
            return True

    if _has("gnome-screenshot"):
        ok, _ = _run(["gnome-screenshot", "-a", "-f", output_path])
        if ok and os.path.isfile(output_path):
            return True

    if _has("grim") and _has("slurp"):
        try:
            slurp = subprocess.run(["slurp"], capture_output=True, text=True, timeout=30, env=external_command_env())
            if slurp.returncode == 0 and slurp.stdout.strip():
                geometry = slurp.stdout.strip()
                ok, _ = _run(["grim", "-g", geometry, output_path])
                if ok and os.path.isfile(output_path):
                    return True
        except (subprocess.SubprocessError, OSError):
            pass

    if _has("scrot"):
        ok, _ = _run(["scrot", "-s", output_path])
        if ok and os.path.isfile(output_path):
            return True

    if _has("maim") and _has("slop"):
        try:
            slop = subprocess.run(["slop", "-f", "%g"], capture_output=True, text=True, timeout=30, env=external_command_env())
            if slop.returncode == 0 and slop.stdout.strip():
                geometry = slop.stdout.strip()
                ok, _ = _run(["maim", "-g", geometry, output_path])
                if ok and os.path.isfile(output_path):
                    return True
        except (subprocess.SubprocessError, OSError):
            pass

    return False


def capture_window(output_path: str) -> bool:
    if IS_MACOS:
        ok, _ = _run(["screencapture", "-w", "-x", output_path])
        return ok and os.path.isfile(output_path)

    portal_path = _portal_screenshot(interactive=True)
    if portal_path:
        try:
            shutil.copy2(portal_path, output_path)
            return True
        except IOError:
            pass
        finally:
            try:
                os.unlink(portal_path)
            except OSError:
                pass

    if _has("spectacle"):
        ok, _ = _run(["spectacle", "-b", "-n", "-a", "-o", output_path])
        if ok and os.path.isfile(output_path):
            return True

    if _has("gnome-screenshot"):
        ok, _ = _run(["gnome-screenshot", "-w", "-f", output_path])
        if ok and os.path.isfile(output_path):
            return True

    if _has("scrot"):
        ok, _ = _run(["scrot", "-u", output_path])
        if ok and os.path.isfile(output_path):
            return True

    if _has("maim") and _has("xdotool"):
        try:
            xdo = subprocess.run(["xdotool", "getactivewindow"], capture_output=True, text=True, timeout=5, env=external_command_env())
            if xdo.returncode == 0:
                window_id = xdo.stdout.strip()
                ok, _ = _run(["maim", "-i", window_id, output_path])
                if ok and os.path.isfile(output_path):
                    return True
        except (subprocess.SubprocessError, OSError):
            pass

    return False


def capture(mode: CaptureMode, output_path: str) -> bool:
    if mode == CaptureMode.FULLSCREEN:
        return capture_fullscreen(output_path)
    if mode == CaptureMode.REGION:
        return capture_region(output_path)
    if mode == CaptureMode.WINDOW:
        return capture_window(output_path)
    return False


def detect_available_backends() -> list[str]:
    backends = []
    if IS_MACOS:
        backends.append("screencapture (macOS)")
        return backends
    if os.path.isfile(packaged_script_path("_portal_helper.py")) or _has("gdbus"):
        backends.append("XDG Portal")
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
