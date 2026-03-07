#!/usr/bin/env python3
"""XDG Desktop Portal helper for BazzCap.

Standalone script that interacts with the XDG Desktop Portal via D-Bus
to take screenshots or start screencasts. Outputs the result path to stdout.

Usage:
    python3 _portal_helper.py screenshot [--interactive|--fullscreen]
    python3 _portal_helper.py screencast --start
    python3 _portal_helper.py screencast --stop
"""

import sys
import os
import signal


def screenshot(interactive=True):
    """Take a screenshot via the XDG Desktop Portal."""
    try:
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib
    except ImportError:
        # dbus-python or PyGObject not available — can't use portal
        sys.exit(1)

    DBusGMainLoop(set_as_default=True)
    loop = GLib.MainLoop()
    bus = dbus.SessionBus()
    result_path = [None]

    def on_response(response, results):
        if response == 0:  # Success
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

        # Timeout after 60 seconds
        GLib.timeout_add_seconds(60, loop.quit)
        loop.run()

    except dbus.exceptions.DBusException:
        sys.exit(1)

    if result_path[0] and os.path.isfile(result_path[0]):
        print(result_path[0])
        sys.exit(0)
    else:
        sys.exit(1)


def screencast_start():
    """Start a screencast via XDG Desktop Portal. Prints PipeWire node ID."""
    try:
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib
    except ImportError:
        sys.exit(1)

    DBusGMainLoop(set_as_default=True)
    loop = GLib.MainLoop()
    bus = dbus.SessionBus()
    node_id = [None]

    portal = bus.get_object(
        "org.freedesktop.portal.Desktop",
        "/org/freedesktop/portal/desktop",
    )
    screencast = dbus.Interface(portal, "org.freedesktop.portal.ScreenCast")

    sender = bus.get_unique_name().replace(".", "_").replace(":", "")
    import time

    # Step 1: Create session
    session_token = f"bazzcap_session_{int(time.time() * 1000)}"
    session_handle = [None]

    def on_create_session(response, results):
        if response == 0:
            session_handle[0] = str(results.get("session_handle", ""))
            # Step 2: Select sources
            select_sources()
        else:
            loop.quit()

    def select_sources():
        token = f"bazzcap_src_{int(time.time() * 1000)}"
        handle_path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"

        bus.add_signal_receiver(
            on_select_sources,
            signal_name="Response",
            dbus_interface="org.freedesktop.portal.Request",
            path=handle_path,
        )

        screencast.SelectSources(
            dbus.ObjectPath(session_handle[0]),
            {
                "types": dbus.UInt32(1 | 2, variant_level=1),  # Monitor + Window
                "handle_token": dbus.String(token, variant_level=1),
            },
        )

    def on_select_sources(response, results):
        if response == 0:
            start_cast()
        else:
            loop.quit()

    def start_cast():
        token = f"bazzcap_start_{int(time.time() * 1000)}"
        handle_path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"

        bus.add_signal_receiver(
            on_start,
            signal_name="Response",
            dbus_interface="org.freedesktop.portal.Request",
            path=handle_path,
        )

        screencast.Start(
            dbus.ObjectPath(session_handle[0]),
            "",
            {"handle_token": dbus.String(token, variant_level=1)},
        )

    def on_start(response, results):
        if response == 0:
            streams = results.get("streams", [])
            if streams:
                node_id[0] = str(streams[0][0])  # PipeWire node ID
        loop.quit()

    # Kick it off
    create_token = f"bazzcap_create_{int(time.time() * 1000)}"
    create_handle = f"/org/freedesktop/portal/desktop/request/{sender}/{create_token}"

    bus.add_signal_receiver(
        on_create_session,
        signal_name="Response",
        dbus_interface="org.freedesktop.portal.Request",
        path=create_handle,
    )

    screencast.CreateSession({
        "session_handle_token": dbus.String(session_token, variant_level=1),
        "handle_token": dbus.String(create_token, variant_level=1),
    })

    GLib.timeout_add_seconds(60, loop.quit)
    loop.run()

    if node_id[0]:
        # Also print session handle so we can close it later
        print(f"{node_id[0]}")
        if session_handle[0]:
            print(f"{session_handle[0]}")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    signal.signal(signal.SIGALRM, lambda *_: sys.exit(1))
    signal.alarm(65)  # Safety timeout

    if len(sys.argv) < 2:
        print("Usage: _portal_helper.py screenshot|screencast [options]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "screenshot":
        interactive = "--interactive" in sys.argv
        screenshot(interactive=interactive)

    elif cmd == "screencast":
        if "--start" in sys.argv:
            screencast_start()
        else:
            print("Usage: _portal_helper.py screencast --start", file=sys.stderr)
            sys.exit(1)

    else:
        sys.exit(1)
