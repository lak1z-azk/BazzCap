"""Global hotkey support for BazzCap.

Wayland-compatible approach:
  1. Unix domain socket IPC at ~/.local/share/bazzcap/bazzcap.sock
     (shared between Flatpak sandbox and host)
  2. GNOME custom keyboard shortcuts via gsettings that trigger a small
     Python one-liner to send commands through the socket
  3. pynput fallback for X11 / XWayland
"""

import os
import socket
import subprocess
import sys
import threading
import shutil
import time

IS_MACOS = sys.platform == "darwin"

# Socket path in user's home dir — shared between Flatpak and host
if IS_MACOS:
    SOCKET_DIR = os.path.expanduser("~/Library/Application Support/bazzcap")
else:
    SOCKET_DIR = os.path.expanduser("~/.local/share/bazzcap")
SOCKET_PATH = os.path.join(SOCKET_DIR, "bazzcap.sock")


class HotkeyManager:
    """Register and manage global hotkeys."""

    def __init__(self):
        self._listeners = {}     # hotkey_name -> callback
        self._bindings = {}      # key_combo -> hotkey_name
        self._running = False
        self._pynput_listener = None
        self._socket_server = None
        self._socket_thread = None

    def register(self, name: str, key_combo: str, callback):
        """Register a global hotkey.

        Args:
            name: Identifier (e.g. 'capture_region')
            key_combo: Key combination (e.g. '<Ctrl>Print')
            callback: Function to call when hotkey triggers
        """
        self._listeners[name] = callback
        self._bindings[key_combo.lower()] = name

    def reregister(self, new_bindings: dict):
        """Re-register hotkeys with new bindings.

        Args:
            new_bindings: dict of {name: key_combo} e.g. {'capture_region': '<Ctrl><Shift>a'}
        """
        # Clear old bindings but keep callbacks
        self._bindings.clear()
        for name, combo in new_bindings.items():
            if combo and name in self._listeners:
                self._bindings[combo.lower()] = name
        # Re-register desktop shortcuts with new bindings
        self._register_desktop_shortcuts()

    def start(self):
        """Start listening for hotkeys."""
        if self._running:
            return
        self._running = True

        # 1. Socket server (primary IPC)
        self._start_socket_server()

        # 2. Register desktop environment shortcuts
        self._register_desktop_shortcuts()

        # 3. pynput fallback (X11)
        try:
            self._start_pynput()
        except Exception:
            pass

    def stop(self):
        """Stop all hotkey listeners and clean up GNOME keybindings."""
        self._running = False

        # Remove GNOME keybindings so they don't block system shortcuts
        self._unregister_desktop_shortcuts()

        if self._pynput_listener:
            try:
                self._pynput_listener.stop()
            except Exception:
                pass
            self._pynput_listener = None

        if self._socket_server:
            try:
                self._socket_server.close()
            except Exception:
                pass
            self._socket_server = None

        try:
            os.unlink(SOCKET_PATH)
        except OSError:
            pass

    # ── Socket IPC Server ────────────────────────────────────────────────

    def _start_socket_server(self):
        """Start Unix domain socket server for receiving hotkey commands."""
        os.makedirs(SOCKET_DIR, exist_ok=True)

        try:
            os.unlink(SOCKET_PATH)
        except OSError:
            pass

        self._socket_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket_server.settimeout(1.0)
        self._socket_server.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o600)
        self._socket_server.listen(5)

        self._socket_thread = threading.Thread(
            target=self._socket_listen_loop, daemon=True
        )
        self._socket_thread.start()

    def _socket_listen_loop(self):
        """Listen for incoming commands on the Unix socket.

        Protocol:  command_name           (no cursor info)
              or:  command_name@x,y       (cursor position from xdotool)
        """
        while self._running:
            try:
                conn, _ = self._socket_server.accept()
                data = conn.recv(256).decode("utf-8", errors="ignore").strip()
                conn.close()

                cursor_pos = None
                name = data
                if "@" in data:
                    name, pos_str = data.split("@", 1)
                    try:
                        cx, cy = pos_str.split(",")
                        cursor_pos = (int(cx), int(cy))
                    except (ValueError, TypeError):
                        pass

                if name in self._listeners:
                    callback = self._listeners[name]
                    try:
                        callback(cursor_pos=cursor_pos)
                    except TypeError:
                        callback()
            except socket.timeout:
                continue
            except (OSError, ConnectionError):
                if self._running:
                    time.sleep(0.5)
                continue

    # ── pynput backend (X11 / XWayland) ──────────────────────────────────

    def _start_pynput(self):
        """Start hotkey listener using pynput (X11/XWayland only)."""
        from pynput import keyboard

        hotkeys_dict = {}
        for combo, name in self._bindings.items():
            callback = self._listeners.get(name)
            if callback:
                pynput_combo = self._to_pynput_combo(combo)
                if pynput_combo:
                    hotkeys_dict[pynput_combo] = callback

        if hotkeys_dict:
            self._pynput_listener = keyboard.GlobalHotKeys(hotkeys_dict)
            self._pynput_listener.start()

    @staticmethod
    def _to_pynput_combo(combo: str) -> str | None:
        """Convert hotkey string to pynput format."""
        combo = combo.strip().lower()

        key_map = {
            "print": "<print_screen>", "printscreen": "<print_screen>",
            "print_screen": "<print_screen>", "delete": "<delete>",
            "escape": "<esc>", "space": "<space>", "enter": "<enter>",
            "return": "<enter>", "tab": "<tab>", "backspace": "<backspace>",
        }

        parts = []
        remaining = combo

        modifiers_map = {
            "<ctrl>": "<ctrl>", "<control>": "<ctrl>",
            "<shift>": "<shift>", "<alt>": "<alt>",
            "<super>": "<cmd>", "<meta>": "<cmd>",
        }

        for mod_in, mod_out in modifiers_map.items():
            if mod_in in remaining:
                parts.append(mod_out)
                remaining = remaining.replace(mod_in, "")

        remaining = remaining.strip()

        if remaining in key_map:
            parts.append(key_map[remaining])
        elif len(remaining) == 1:
            parts.append(remaining)
        elif remaining:
            parts.append(f"<{remaining}>")

        return "+".join(parts) if parts else None

    # ── Desktop environment shortcuts ────────────────────────────────────

    def _gs_runner(self):
        """Return a gsettings runner function, or None if unavailable."""
        in_flatpak = (
            os.path.isfile("/.flatpak-info")
            or "FLATPAK_ID" in os.environ
            or os.environ.get("container") == "flatpak"
            or any(p.startswith("/app/")
                   for p in os.environ.get("PATH", "").split(":"))
        )
        if in_flatpak:
            if not shutil.which("flatpak-spawn"):
                return None
            use_flatpak = True
        elif shutil.which("gsettings"):
            use_flatpak = False
        else:
            return None

        def gs(*args):
            if use_flatpak:
                cmd = ["flatpak-spawn", "--host", "gsettings"] + list(args)
            else:
                cmd = ["gsettings"] + list(args)
            return subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return gs

    def _unregister_desktop_shortcuts(self):
        """Remove BazzCap shortcuts from the desktop environment."""
        if IS_MACOS:
            return  # macOS uses pynput only, no DE shortcuts
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        if "gnome" in desktop:
            self._unregister_gnome_shortcuts()
        elif "kde" in desktop or "plasma" in desktop:
            self._unregister_kde_shortcuts()

    def _unregister_gnome_shortcuts(self):
        """Remove all bazzcap custom keybindings from GNOME."""
        gs = self._gs_runner()
        if gs is None:
            return

        schema = "org.gnome.settings-daemon.plugins.media-keys"
        key = "custom-keybindings"

        try:
            result = gs("get", schema, key)
            existing = result.stdout.strip()
            if existing == "@as []" or not existing:
                return
            existing_list = [
                p.strip().strip("'\"")
                for p in existing.strip("[]").split(",")
                if p.strip()
            ]
        except Exception:
            return

        # Remove bazzcap entries, reset their bindings
        non_bazzcap = []
        for path in existing_list:
            if "bazzcap" in path:
                binding_schema = f"{schema}.custom-keybinding:{path}"
                try:
                    gs("reset", binding_schema, "name")
                    gs("reset", binding_schema, "command")
                    gs("reset", binding_schema, "binding")
                except Exception:
                    pass
            else:
                non_bazzcap.append(path)

        # Update the list to only non-bazzcap entries
        if non_bazzcap:
            paths_str = "[" + ", ".join(f"'{p}'" for p in non_bazzcap) + "]"
        else:
            paths_str = "@as []"
        try:
            gs("set", schema, key, paths_str)
        except Exception:
            pass

        # Restore GNOME's default Print key (show-screenshot-ui) since
        # BazzCap is no longer capturing with any custom keybinding.
        self._restore_gnome_print_key(gs)

    def _register_desktop_shortcuts(self):
        """Register shortcuts with GNOME or KDE."""
        if IS_MACOS:
            return  # macOS uses pynput only
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        if "gnome" in desktop:
            self._register_gnome_shortcuts()
        elif "kde" in desktop or "plasma" in desktop:
            self._register_kde_shortcuts()

    def _register_gnome_shortcuts(self):
        """Register custom shortcuts via GNOME gsettings."""
        gs = self._gs_runner()
        if gs is None:
            return
        schema = "org.gnome.settings-daemon.plugins.media-keys"
        key = "custom-keybindings"
        base_path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"

        # Read existing custom keybindings
        try:
            result = gs("get", schema, key)
            existing = result.stdout.strip()
            if existing == "@as []" or not existing:
                existing_list = []
            else:
                existing_list = [
                    p.strip().strip("'\"")
                    for p in existing.strip("[]").split(",")
                    if p.strip()
                ]
        except Exception:
            existing_list = []

        # Remove old bazzcap entries that are NO LONGER in our bindings
        # but preserve entries the user may have customized
        bazzcap_existing = {p for p in existing_list if "bazzcap" in p}
        non_bazzcap = [p for p in existing_list if "bazzcap" not in p]

        display_names = {
            "capture_fullscreen": "BazzCap: Fullscreen",
            "capture_region": "BazzCap: Region",
            "capture_window": "BazzCap: Window",
        }

        new_entries = []
        for combo, name in self._bindings.items():
            path = f"{base_path}/bazzcap-{name}/"
            binding_schema = f"{schema}.custom-keybinding:{path}"

            display = display_names.get(name, f"BazzCap: {name}")

            # Copy the trigger script to ~/.local/share/bazzcap/ (no spaces)
            # so GNOME Shell can parse the command correctly.
            src_trigger = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "_trigger.py"
            )
            dst_trigger = os.path.join(SOCKET_DIR, "_trigger.py")
            try:
                import shutil as _shutil
                _shutil.copy2(src_trigger, dst_trigger)
            except OSError:
                pass
            trigger_cmd = f"python3 {dst_trigger} {name}"

            if path in bazzcap_existing:
                # Entry exists — update command AND binding
                try:
                    gs("set", binding_schema, "command", trigger_cmd)
                    gnome_combo = self._to_gnome_combo(combo)
                    gs("set", binding_schema, "binding", gnome_combo)
                except (subprocess.SubprocessError, OSError):
                    pass
                new_entries.append(path)
                bazzcap_existing.discard(path)
                continue

            gnome_combo = self._to_gnome_combo(combo)

            try:
                gs("set", binding_schema, "name", display)
                gs("set", binding_schema, "command", trigger_cmd)
                gs("set", binding_schema, "binding", gnome_combo)
                new_entries.append(path)
            except (subprocess.SubprocessError, OSError):
                pass

        # Update the custom-keybindings list
        # non_bazzcap = other apps' entries
        # new_entries = our entries (existing preserved + newly created)
        all_paths = non_bazzcap + new_entries
        if all_paths:
            paths_str = "[" + ", ".join(f"'{p}'" for p in all_paths) + "]"
            try:
                gs("set", schema, key, paths_str)
            except (subprocess.SubprocessError, OSError):
                pass

        # Manage the system Print key: if BazzCap is using bare "Print"
        # as a custom keybinding, suppress GNOME's built-in screenshot UI.
        # If BazzCap is NOT using "Print", restore GNOME's default.
        bazzcap_uses_print = any(
            self._to_gnome_combo(c) == "Print" for c in self._bindings
        )
        self._manage_gnome_print_key(gs, bazzcap_uses_print)

    @staticmethod
    def _manage_gnome_print_key(gs, bazzcap_owns_print: bool):
        """Manage GNOME's show-screenshot-ui keybinding for the Print key.

        GNOME's default is Print → show-screenshot-ui (interactive screenshot).
        When BazzCap claims Print for fullscreen capture, the custom keybinding
        overrides the shell keybinding.  When BazzCap releases Print (user
        changed to a different key), we restore the GNOME default so the
        native screenshot UI works again.
        """
        shell_schema = "org.gnome.shell.keybindings"
        shell_key = "show-screenshot-ui"
        try:
            if bazzcap_owns_print:
                # BazzCap is using Print — clear the shell binding to avoid
                # any potential conflict (custom keybindings take priority
                # anyway, but this keeps things clean).
                gs("set", shell_schema, shell_key, "@as []")
            else:
                # BazzCap is NOT using Print — restore GNOME's default so
                # the native interactive screenshot UI works on Print.
                gs("set", shell_schema, shell_key, "['Print']")
        except (subprocess.SubprocessError, OSError):
            pass

    @staticmethod
    def _restore_gnome_print_key(gs):
        """Restore GNOME's default Print → show-screenshot-ui binding."""
        try:
            gs("set", "org.gnome.shell.keybindings",
               "show-screenshot-ui", "['Print']")
        except (subprocess.SubprocessError, OSError):
            pass

    @staticmethod
    def _to_gnome_combo(combo: str) -> str:
        """Convert hotkey string to GNOME keybinding format."""
        combo = combo.strip().lower()

        key_map = {
            "print": "Print", "printscreen": "Print",
            "print_screen": "Print", "delete": "Delete",
            "escape": "Escape", "space": "space",
            "enter": "Return", "return": "Return",
            "tab": "Tab", "backspace": "BackSpace",
        }

        parts = []
        remaining = combo

        for mod in ["<ctrl>", "<control>", "<shift>", "<alt>",
                     "<super>", "<meta>"]:
            gnome_mod = {
                "<ctrl>": "<Ctrl>", "<control>": "<Ctrl>",
                "<shift>": "<Shift>", "<alt>": "<Alt>",
                "<super>": "<Super>", "<meta>": "<Super>",
            }.get(mod, "")
            if mod in remaining:
                parts.append(gnome_mod)
                remaining = remaining.replace(mod, "")

        remaining = remaining.strip()
        if remaining in key_map:
            parts.append(key_map[remaining])
        elif len(remaining) == 1:
            parts.append(remaining.lower())
        elif remaining:
            parts.append(remaining.capitalize())

        return "".join(parts)

    def _register_kde_shortcuts(self):
        """Register custom shortcuts on KDE Plasma via .desktop shortcut files.

        Creates .desktop files in ~/.local/share/applications/ with
        X-KDE-Shortcuts, then uses kglobalaccel6 D-Bus or kwriteconfig
        to register them as global shortcuts.
        """
        apps_dir = os.path.expanduser("~/.local/share/applications")
        os.makedirs(apps_dir, exist_ok=True)

        # Copy the trigger script
        src_trigger = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "_trigger.py"
        )
        dst_trigger = os.path.join(SOCKET_DIR, "_trigger.py")
        try:
            import shutil as _shutil
            _shutil.copy2(src_trigger, dst_trigger)
        except OSError:
            pass

        display_names = {
            "capture_fullscreen": "BazzCap: Fullscreen",
            "capture_region": "BazzCap: Region",
            "capture_window": "BazzCap: Window",
        }

        for combo, name in self._bindings.items():
            kde_combo = self._to_kde_combo(combo)
            display = display_names.get(name, f"BazzCap: {name}")
            trigger_cmd = f"python3 {dst_trigger} {name}"
            desktop_id = f"bazzcap-{name}"
            desktop_path = os.path.join(apps_dir, f"{desktop_id}.desktop")

            desktop_content = (
                "[Desktop Entry]\n"
                f"Name={display}\n"
                f"Exec={trigger_cmd}\n"
                "Type=Application\n"
                "NoDisplay=true\n"
                "Terminal=false\n"
                f"X-KDE-Shortcuts={kde_combo}\n"
            )
            try:
                with open(desktop_path, "w") as f:
                    f.write(desktop_content)
                os.chmod(desktop_path, 0o755)
            except OSError:
                continue

            # Register via kglobalaccel D-Bus
            try:
                # Try qdbus6 first, then qdbus
                qdbus = None
                for tool in ("qdbus6", "qdbus"):
                    if shutil.which(tool):
                        qdbus = tool
                        break

                if qdbus:
                    # Tell KDE to reload shortcuts from the .desktop file
                    subprocess.run(
                        [qdbus, "org.kde.KGlobalAccel",
                         "/kglobalaccel",
                         "org.kde.KGlobalAccel.blockGlobalShortcuts", "false"],
                        capture_output=True, timeout=5,
                    )

                # Also write to kglobalshortcutsrc as fallback
                # (picked up on next login if D-Bus doesn't work)
                kwrite = None
                for tool in ("kwriteconfig6", "kwriteconfig5"):
                    if shutil.which(tool):
                        kwrite = tool
                        break
                if kwrite:
                    shortcut_val = f"{kde_combo},none,{display}"
                    subprocess.run(
                        [kwrite, "--file", "kglobalshortcutsrc",
                         "--group", f"{desktop_id}.desktop",
                         "--key", "_launch", shortcut_val],
                        capture_output=True, timeout=5,
                    )
            except (subprocess.SubprocessError, OSError):
                pass

        # Tell KDE to re-read configs
        try:
            subprocess.run(
                ["dbus-send", "--type=signal", "--dest=org.kde.KGlobalAccel",
                 "/kglobalaccel", "org.kde.KGlobalAccel.yourShortcutsChanged",
                 "array:string:"],
                capture_output=True, timeout=5,
            )
        except (subprocess.SubprocessError, OSError):
            pass

    def _unregister_kde_shortcuts(self):
        """Remove BazzCap shortcuts from KDE."""
        apps_dir = os.path.expanduser("~/.local/share/applications")
        shortcut_names = [
            "capture_fullscreen", "capture_region", "capture_window",
        ]
        for name in shortcut_names:
            desktop_id = f"bazzcap-{name}"
            desktop_path = os.path.join(apps_dir, f"{desktop_id}.desktop")
            try:
                os.unlink(desktop_path)
            except OSError:
                pass

            # Remove from kglobalshortcutsrc
            kwrite = None
            for tool in ("kwriteconfig6", "kwriteconfig5"):
                if shutil.which(tool):
                    kwrite = tool
                    break
            if kwrite:
                try:
                    subprocess.run(
                        [kwrite, "--file", "kglobalshortcutsrc",
                         "--group", f"{desktop_id}.desktop",
                         "--key", "_launch", "--delete"],
                        capture_output=True, timeout=5,
                    )
                except (subprocess.SubprocessError, OSError):
                    pass

    @staticmethod
    def _to_kde_combo(combo: str) -> str:
        """Convert hotkey string to KDE keybinding format (e.g. 'Ctrl+Shift+Print')."""
        combo = combo.strip().lower()
        key_map = {
            "print": "Print", "printscreen": "Print",
            "print_screen": "Print", "delete": "Delete",
            "escape": "Escape", "space": "Space",
            "enter": "Return", "return": "Return",
            "tab": "Tab", "backspace": "Backspace",
        }

        parts = []
        remaining = combo
        for mod_in, mod_out in [
            ("<ctrl>", "Ctrl"), ("<control>", "Ctrl"),
            ("<shift>", "Shift"), ("<alt>", "Alt"),
            ("<super>", "Meta"), ("<meta>", "Meta"),
        ]:
            if mod_in in remaining:
                parts.append(mod_out)
                remaining = remaining.replace(mod_in, "")

        remaining = remaining.strip()
        if remaining in key_map:
            parts.append(key_map[remaining])
        elif len(remaining) == 1:
            parts.append(remaining.upper())
        elif remaining:
            parts.append(remaining.capitalize())

        return "+".join(parts)

    def is_available(self) -> bool:
        """Check if any hotkey backend is available."""
        return True
