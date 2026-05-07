#!/usr/bin/env python3

import sys
import os
import signal
import shutil
import tempfile


def _shared_temp_dir() -> str:
    """Return a temp directory visible from both host and Flatpak sandboxes.

    /tmp is sandboxed inside Flatpak, so files created on the host are
    invisible to the app.  Use ~/.config/bazzcap/ which lives on the shared
    home filesystem.
    """
    d = os.path.join(os.path.expanduser("~"), ".config", "bazzcap")
    os.makedirs(d, exist_ok=True)
    return d


def _stage_portal_capture(path: str) -> str | None:
    """Move the portal-created screenshot into a temporary file.

    Some portals persist captures into the user's screenshots folder before
    returning the path. BazzCap only needs the pixels, so we stage them in a
    temp file and remove the portal artifact to avoid duplicate saved images.
    """
    if not path or not os.path.isfile(path):
        return None

    fd, tmp_path = tempfile.mkstemp(prefix="bazzcap_portal_", suffix=".png",
                                    dir=_shared_temp_dir())
    os.close(fd)
    try:
        shutil.copy2(path, tmp_path)
        try:
            os.unlink(path)
        except OSError:
            pass
        return tmp_path
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return None


def screenshot(interactive=True):
    try:
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib
    except ImportError:
        sys.exit(1)

    DBusGMainLoop(set_as_default=True)
    loop = GLib.MainLoop()
    bus = dbus.SessionBus()
    result_path = [None]

    def on_response(response, results):
        if response == 0:
            uri = str(results.get("uri", ""))
            if uri.startswith("file://"):
                uri = uri[7:]
            result_path[0] = uri
        loop.quit()

    try:
        portal = bus.get_object(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
        )
        iface = dbus.Interface(portal, "org.freedesktop.portal.Screenshot")

        sender = bus.get_unique_name().replace(".", "_").replace(":", "")
        import time
        token = f"bazzcap_{int(time.time() * 1000)}"
        handle_path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"

        bus.add_signal_receiver(
            on_response,
            signal_name="Response",
            dbus_interface="org.freedesktop.portal.Request",
            path=handle_path,
        )

        options = {
            "interactive": dbus.Boolean(interactive, variant_level=1),
            "handle_token": dbus.String(token, variant_level=1),
        }

        iface.Screenshot("", options)

        GLib.timeout_add_seconds(15, loop.quit)
        loop.run()

    except dbus.exceptions.DBusException:
        sys.exit(1)

    staged_path = _stage_portal_capture(result_path[0])
    if staged_path:
        print(staged_path)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    signal.signal(signal.SIGALRM, lambda *_: sys.exit(1))
    signal.alarm(20)

    if len(sys.argv) < 2:
        print("Usage: _portal_helper.py screenshot [options]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "screenshot":
        interactive = "--interactive" in sys.argv
        screenshot(interactive=interactive)
    else:
        sys.exit(1)
