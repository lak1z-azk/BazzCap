import os
import re
import shutil
import subprocess
import sys
import time
from enum import Enum, auto
from urllib.parse import unquote, urlparse

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

    return _gdbus_portal_screenshot(interactive)


_EMBEDDED_HELPER_MARKER = "bazzcap_embedded_portal_helper"


def _embedded_helper_path() -> str | None:
    """Materialise a copy of _portal_helper.py when it is missing from the bundle.

    A PyInstaller build that drops the bundled helper (this shipped as 1.1.0)
    leaves no working screenshot path on Wayland at all.  Rather than fail, write
    the helper source — read from this package if present, else the inlined copy
    below — to a cached temp file and run that.
    """
    cache_dir = os.path.join(os.path.expanduser("~"), ".config", "bazzcap")
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except OSError:
        cache_dir = tempfile.gettempdir()

    target = os.path.join(cache_dir, "_portal_helper_fallback.py")
    if os.path.isfile(target):
        return target

    try:
        with open(target, "w") as f:
            f.write(_PORTAL_HELPER_SOURCE)
        os.chmod(target, 0o700)
        return target
    except OSError:
        return None


def _gdbus_portal_screenshot(interactive: bool) -> str | None:
    """Last-resort portal screenshot using the embedded helper.

    Note this cannot be done with the gdbus CLI: Screenshot() returns only a
    Request object path, and the image URI arrives later as a Response signal
    unicast to the *caller's* bus name.  A separate `gdbus monitor` process
    never receives it, and the `gdbus call` process that would has already
    exited.  The call and the signal subscription must share one live
    connection, which is exactly what the helper does.
    """
    helper = _embedded_helper_path()
    if not helper:
        return None

    args = [helper, "screenshot",
            "--interactive" if interactive else "--fullscreen"]
    for python_cmd in iter_python_commands(prefer_host=is_flatpak()):
        try:
            result = subprocess.run(
                python_cmd + args,
                capture_output=True,
                text=True,
                timeout=30,
                env=external_command_env(),
            )
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip()
                if os.path.isfile(path):
                    return path
        except (subprocess.SubprocessError, OSError):
            continue
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


# ---------------------------------------------------------------------------
# Inlined copy of _portal_helper.py, used only when the bundled file is
# missing from a build.  Regenerate with scripts/sync_embedded_helper.py.
# ---------------------------------------------------------------------------

_PORTAL_HELPER_SOURCE = (
    '#!/usr/bin/env python3\n'
    '\n'
    'import sys\n'
    'import os\n'
    'import signal\n'
    'import shutil\n'
    'import tempfile\n'
    '\n'
    '\n'
    'def _shared_temp_dir() -> str:\n'
    '    """Return a temp directory visible from both host and Flatpak sandboxes.\n'
    '\n'
    '    /tmp is sandboxed inside Flatpak, so files created on the host are\n'
    '    invisible to the app.  Use ~/.config/bazzcap/ which lives on the shared\n'
    '    home filesystem.\n'
    '    """\n'
    '    d = os.path.join(os.path.expanduser("~"), ".config", "bazzcap")\n'
    '    os.makedirs(d, exist_ok=True)\n'
    '    return d\n'
    '\n'
    '\n'
    'def _stage_portal_capture(path: str) -> str | None:\n'
    '    """Move the portal-created screenshot into a temporary file.\n'
    '\n'
    "    Some portals persist captures into the user's screenshots folder before\n"
    '    returning the path. BazzCap only needs the pixels, so we stage them in a\n'
    '    temp file and remove the portal artifact to avoid duplicate saved images.\n'
    '    """\n'
    '    if not path or not os.path.isfile(path):\n'
    '        return None\n'
    '\n'
    '    fd, tmp_path = tempfile.mkstemp(prefix="bazzcap_portal_", suffix=".png",\n'
    '                                    dir=_shared_temp_dir())\n'
    '    os.close(fd)\n'
    '    try:\n'
    '        shutil.copy2(path, tmp_path)\n'
    '        try:\n'
    '            os.unlink(path)\n'
    '        except OSError:\n'
    '            pass\n'
    '        return tmp_path\n'
    '    except OSError:\n'
    '        try:\n'
    '            os.unlink(tmp_path)\n'
    '        except OSError:\n'
    '            pass\n'
    '        return None\n'
    '\n'
    '\n'
    'def screenshot(interactive=True):\n'
    '    try:\n'
    '        import dbus\n'
    '        from dbus.mainloop.glib import DBusGMainLoop\n'
    '        from gi.repository import GLib\n'
    '    except ImportError:\n'
    '        sys.exit(1)\n'
    '\n'
    '    DBusGMainLoop(set_as_default=True)\n'
    '    loop = GLib.MainLoop()\n'
    '    bus = dbus.SessionBus()\n'
    '    result_path = [None]\n'
    '\n'
    '    def on_response(response, results):\n'
    '        if response == 0:\n'
    '            uri = str(results.get("uri", ""))\n'
    '            if uri.startswith("file://"):\n'
    '                uri = uri[7:]\n'
    '            result_path[0] = uri\n'
    '        loop.quit()\n'
    '\n'
    '    try:\n'
    '        portal = bus.get_object(\n'
    '            "org.freedesktop.portal.Desktop",\n'
    '            "/org/freedesktop/portal/desktop",\n'
    '        )\n'
    '        iface = dbus.Interface(portal, "org.freedesktop.portal.Screenshot")\n'
    '\n'
    '        sender = bus.get_unique_name().replace(".", "_").replace(":", "")\n'
    '        import time\n'
    '        token = f"bazzcap_{int(time.time() * 1000)}"\n'
    '        handle_path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"\n'
    '\n'
    '        bus.add_signal_receiver(\n'
    '            on_response,\n'
    '            signal_name="Response",\n'
    '            dbus_interface="org.freedesktop.portal.Request",\n'
    '            path=handle_path,\n'
    '        )\n'
    '\n'
    '        options = {\n'
    '            "interactive": dbus.Boolean(interactive, variant_level=1),\n'
    '            "handle_token": dbus.String(token, variant_level=1),\n'
    '        }\n'
    '\n'
    '        iface.Screenshot("", options)\n'
    '\n'
    '        GLib.timeout_add_seconds(15, loop.quit)\n'
    '        loop.run()\n'
    '\n'
    '    except dbus.exceptions.DBusException:\n'
    '        sys.exit(1)\n'
    '\n'
    '    staged_path = _stage_portal_capture(result_path[0])\n'
    '    if staged_path:\n'
    '        print(staged_path)\n'
    '        sys.exit(0)\n'
    '    else:\n'
    '        sys.exit(1)\n'
    '\n'
    '\n'
    'if __name__ == "__main__":\n'
    '    signal.signal(signal.SIGALRM, lambda *_: sys.exit(1))\n'
    '    signal.alarm(20)\n'
    '\n'
    '    if len(sys.argv) < 2:\n'
    '        print("Usage: _portal_helper.py screenshot [options]", file=sys.stderr)\n'
    '        sys.exit(1)\n'
    '\n'
    '    cmd = sys.argv[1]\n'
    '\n'
    '    if cmd == "screenshot":\n'
    '        interactive = "--interactive" in sys.argv\n'
    '        screenshot(interactive=interactive)\n'
    '    else:\n'
    '        sys.exit(1)\n'
)
