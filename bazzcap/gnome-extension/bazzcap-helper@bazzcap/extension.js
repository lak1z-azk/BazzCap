/* BazzCap Helper — GNOME Shell extension
 *
 * Exposes a D-Bus method to return the connector name of the monitor
 * the mouse cursor is currently on.  BazzCap uses this for fullscreen
 * capture on Wayland where cursor position is not available to apps.
 *
 * D-Bus service:  (registered under org.gnome.Shell)
 * Object path:    /org/bazzcap/Helper
 * Method:         GetCursorMonitor() → (s connector, i cursor_x, i cursor_y,
 *                                        i mon_x, i mon_y, i mon_w, i mon_h)
 */

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const DBUS_IFACE = `<node>
  <interface name="org.bazzcap.Helper">
    <method name="GetCursorMonitor">
      <arg type="s" direction="out" name="connector"/>
      <arg type="i" direction="out" name="x"/>
      <arg type="i" direction="out" name="y"/>
      <arg type="i" direction="out" name="mon_x"/>
      <arg type="i" direction="out" name="mon_y"/>
      <arg type="i" direction="out" name="mon_w"/>
      <arg type="i" direction="out" name="mon_h"/>
    </method>
  </interface>
</node>`;

export default class BazzCapHelperExtension {
    enable() {
        const nodeInfo = Gio.DBusNodeInfo.new_for_xml(DBUS_IFACE);

        this._dbusId = Gio.DBus.session.register_object(
            '/org/bazzcap/Helper',
            nodeInfo.interfaces[0],
            (connection, sender, path, iface, method, params, invocation) => {
                try {
                    if (method === 'GetCursorMonitor') {
                        const [x, y, _mods] = global.get_pointer();

                        let connector = '';
                        let monX = 0, monY = 0, monW = 0, monH = 0;

                        /* Strategy 1 (GNOME 45+ / Mutter 14+):
                         * global.backend.get_current_logical_monitor()
                         * -> logicalMonitor.get_monitors()[0].get_connector()
                         */
                        try {
                            const logMon = global.backend.get_current_logical_monitor();
                            if (logMon) {
                                const monitors = logMon.get_monitors();
                                if (monitors && monitors.length > 0)
                                    connector = monitors[0].get_connector() || '';
                            }
                        } catch (_e1) {
                            /* Strategy 1 failed — try strategy 2 */
                        }

                        /* Strategy 2 fallback: display index + geometry
                         * Works on any GNOME Shell version.
                         */
                        const monIdx = global.display.get_current_monitor();
                        const rect = global.display.get_monitor_geometry(monIdx);
                        if (rect) {
                            monX = rect.x;
                            monY = rect.y;
                            monW = rect.width;
                            monH = rect.height;
                        }

                        /* If strategy 1 didn't yield a connector,
                         * try iterating all logical monitors to match by index.
                         */
                        if (!connector) {
                            try {
                                const mgr = global.backend.get_monitor_manager();
                                if (mgr) {
                                    const logMons = mgr.get_logical_monitors();
                                    for (const lm of logMons) {
                                        if (lm.get_number() === monIdx) {
                                            const mons = lm.get_monitors();
                                            if (mons && mons.length > 0)
                                                connector = mons[0].get_connector() || '';
                                            break;
                                        }
                                    }
                                }
                            } catch (_e2) {
                                /* No luck — connector stays empty */
                            }
                        }

                        invocation.return_value(
                            new GLib.Variant('(siiiiii)', [
                                connector, x, y, monX, monY, monW, monH
                            ])
                        );
                    }
                } catch (e) {
                    invocation.return_error_literal(
                        Gio.DBusError,
                        Gio.DBusError.FAILED,
                        e.message || 'unknown error'
                    );
                }
            },
            null,
            null
        );
    }

    disable() {
        if (this._dbusId) {
            Gio.DBus.session.unregister_object(this._dbusId);
            this._dbusId = null;
        }
    }
}
