#!/usr/bin/env python3

import sys
import os
import signal


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

        GLib.timeout_add_seconds(60, loop.quit)
        loop.run()

    except dbus.exceptions.DBusException:
        sys.exit(1)

    if result_path[0] and os.path.isfile(result_path[0]):
        print(result_path[0])
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    signal.signal(signal.SIGALRM, lambda *_: sys.exit(1))
    signal.alarm(65)

    if len(sys.argv) < 2:
        print("Usage: _portal_helper.py screenshot [options]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "screenshot":
        interactive = "--interactive" in sys.argv
        screenshot(interactive=interactive)
    else:
        sys.exit(1)
