"""Hotkey configuration dialog for BazzCap — allows users to set custom shortcuts."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QDialogButtonBox, QMessageBox,
    QLineEdit, QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QKeyEvent, QKeySequence


class HotkeyEdit(QLineEdit):
    """Custom line edit that captures key combinations when focused.

    Properly handles modifier keys (Ctrl, Shift, Alt, Super) and multi-key
    combos on Linux/Wayland by intercepting events before QLineEdit processes
    them, and grabbing the keyboard during recording.
    """

    hotkey_changed = pyqtSignal(str)

    # Keys that are only modifiers — not valid on their own
    _MODIFIER_KEYS = {
        Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt,
        Qt.Key.Key_Meta, Qt.Key.Key_Super_L, Qt.Key.Key_Super_R,
        Qt.Key.Key_AltGr, Qt.Key.Key_Hyper_L, Qt.Key.Key_Hyper_R,
    }

    def __init__(self, current_hotkey: str = "", parent=None):
        super().__init__(parent)
        self._hotkey = current_hotkey
        self._recording = False
        self._held_modifiers = Qt.KeyboardModifier(0)
        self.setText(self._format_display(current_hotkey))
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(200)
        self.setPlaceholderText("Click to set hotkey")
        self.setStyleSheet("""
            QLineEdit {
                background: #2a2a2a;
                color: #ddd;
                border: 2px solid #555;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 13px;
                font-family: monospace;
            }
            QLineEdit:focus {
                border-color: #4488ff;
                background: #1a1a3a;
            }
        """)

    @property
    def hotkey(self):
        return self._hotkey

    def _start_recording(self):
        """Enter recording mode — grab keyboard to intercept all keys."""
        self._recording = True
        self._held_modifiers = Qt.KeyboardModifier(0)
        self.setText("Press a key combination...")
        self.setStyleSheet(self.styleSheet().replace("#555", "#ff8800"))
        self.grabKeyboard()

    def _stop_recording(self):
        """Exit recording mode — release keyboard grab."""
        self._recording = False
        self._held_modifiers = Qt.KeyboardModifier(0)
        self.releaseKeyboard()
        self.setStyleSheet(self.styleSheet().replace("#ff8800", "#555"))

    def mousePressEvent(self, event):
        """Start recording when clicked."""
        if not self._recording:
            self._start_recording()
        super().mousePressEvent(event)

    def event(self, event) -> bool:
        """Intercept ALL key events before QLineEdit can process them.

        This prevents Ctrl+A from triggering 'Select All' and similar issues.
        """
        if self._recording and event.type() in (
            QEvent.Type.KeyPress, QEvent.Type.KeyRelease,
            QEvent.Type.ShortcutOverride,
        ):
            if event.type() == QEvent.Type.ShortcutOverride:
                # Accept shortcut override to prevent system shortcuts
                event.accept()
                return True

            if event.type() == QEvent.Type.KeyPress:
                self._handle_key_press(event)
                return True

            if event.type() == QEvent.Type.KeyRelease:
                return True  # swallow releases too

        return super().event(event)

    def _handle_key_press(self, event: QKeyEvent):
        """Process captured key press."""
        key = event.key()
        modifiers = event.modifiers()

        # Escape always cancels
        if key == Qt.Key.Key_Escape and not (
            modifiers & ~Qt.KeyboardModifier.KeypadModifier
        ):
            self._stop_recording()
            self.setText(self._format_display(self._hotkey))
            return

        # If it's a standalone modifier key, show live preview but don't commit
        if key in self._MODIFIER_KEYS:
            self._held_modifiers = modifiers
            preview = self._modifiers_to_display(modifiers)
            if preview:
                self.setText(preview + " + ...")
            return

        # Non-modifier key pressed — commit the binding
        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("<Ctrl>")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("<Shift>")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("<Alt>")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("<Super>")

        # Resolve the actual key name (ignore shift-modified key values)
        key_name = self._key_to_name(key)
        if not key_name:
            return  # Unknown key, ignore

        parts.append(key_name)
        self._hotkey = "".join(parts)
        self._stop_recording()
        self.setText(self._format_display(self._hotkey))
        self.hotkey_changed.emit(self._hotkey)

    def focusOutEvent(self, event):
        """Cancel recording on focus loss."""
        if self._recording:
            self._stop_recording()
            self.setText(self._format_display(self._hotkey))
        super().focusOutEvent(event)

    @staticmethod
    def _modifiers_to_display(modifiers) -> str:
        """Convert modifier flags to display string for live preview."""
        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("Super")
        return " + ".join(parts)

    @staticmethod
    def _key_to_name(key: int) -> str:
        """Convert Qt key code to a GNOME-compatible key name."""
        key_map = {
            Qt.Key.Key_Print: "Print",
            Qt.Key.Key_F1: "F1", Qt.Key.Key_F2: "F2", Qt.Key.Key_F3: "F3",
            Qt.Key.Key_F4: "F4", Qt.Key.Key_F5: "F5", Qt.Key.Key_F6: "F6",
            Qt.Key.Key_F7: "F7", Qt.Key.Key_F8: "F8", Qt.Key.Key_F9: "F9",
            Qt.Key.Key_F10: "F10", Qt.Key.Key_F11: "F11", Qt.Key.Key_F12: "F12",
            Qt.Key.Key_Space: "space",
            Qt.Key.Key_Return: "Return", Qt.Key.Key_Enter: "Return",
            Qt.Key.Key_Tab: "Tab",
            Qt.Key.Key_Backspace: "BackSpace",
            Qt.Key.Key_Delete: "Delete",
            Qt.Key.Key_Home: "Home", Qt.Key.Key_End: "End",
            Qt.Key.Key_PageUp: "Page_Up", Qt.Key.Key_PageDown: "Page_Down",
            Qt.Key.Key_Insert: "Insert",
            Qt.Key.Key_Up: "Up", Qt.Key.Key_Down: "Down",
            Qt.Key.Key_Left: "Left", Qt.Key.Key_Right: "Right",
            Qt.Key.Key_Pause: "Pause",
            Qt.Key.Key_ScrollLock: "Scroll_Lock",
            Qt.Key.Key_SysReq: "SysReq",
            Qt.Key.Key_CapsLock: "Caps_Lock",
            Qt.Key.Key_NumLock: "Num_Lock",
            Qt.Key.Key_Menu: "Menu",
            # Numpad
            Qt.Key.Key_0: "0", Qt.Key.Key_1: "1", Qt.Key.Key_2: "2",
            Qt.Key.Key_3: "3", Qt.Key.Key_4: "4", Qt.Key.Key_5: "5",
            Qt.Key.Key_6: "6", Qt.Key.Key_7: "7", Qt.Key.Key_8: "8",
            Qt.Key.Key_9: "9",
            Qt.Key.Key_Minus: "minus", Qt.Key.Key_Equal: "equal",
            Qt.Key.Key_BracketLeft: "bracketleft",
            Qt.Key.Key_BracketRight: "bracketright",
            Qt.Key.Key_Semicolon: "semicolon",
            Qt.Key.Key_Apostrophe: "apostrophe",
            Qt.Key.Key_Comma: "comma", Qt.Key.Key_Period: "period",
            Qt.Key.Key_Slash: "slash", Qt.Key.Key_Backslash: "backslash",
            Qt.Key.Key_QuoteLeft: "grave",
        }

        if key in key_map:
            return key_map[key]

        # Standard letter keys (A-Z) — always use lowercase for GNOME compat
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return chr(key).lower()

        # Try QKeySequence as fallback
        seq = QKeySequence(key)
        s = seq.toString()
        return s if s else None

    @staticmethod
    def _format_display(hotkey: str) -> str:
        """Format hotkey string for display."""
        if not hotkey:
            return "(none — click to set)"
        # Convert <Ctrl><Shift>a → Ctrl + Shift + A
        display = hotkey
        display = display.replace("<Ctrl>", "Ctrl + ")
        display = display.replace("<Shift>", "Shift + ")
        display = display.replace("<Alt>", "Alt + ")
        display = display.replace("<Super>", "Super + ")
        # Capitalize the final key for display
        parts = display.strip(" +").split(" + ")
        if parts:
            parts[-1] = parts[-1].upper() if len(parts[-1]) == 1 else parts[-1].title()
        display = " + ".join(parts)
        return display


class HotkeySettingsDialog(QDialog):
    """Dialog for configuring global hotkeys."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("BazzCap — Hotkey Settings")
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Instructions
        info = QLabel(
            "Click on a hotkey field and press your desired key combination.\n"
            "Press Escape while recording to cancel. Leave blank to disable."
        )
        info.setStyleSheet("color: #aaa; padding: 8px; font-size: 11px;")
        layout.addWidget(info)

        # Capture hotkeys
        capture_group = QGroupBox("Screenshot Hotkeys")
        capture_form = QFormLayout()

        hotkeys = self._config.get("hotkeys", {})

        self._hk_fullscreen = HotkeyEdit(hotkeys.get("capture_fullscreen", "Print"))
        capture_form.addRow("Capture Fullscreen:", self._hk_fullscreen)

        self._hk_region = HotkeyEdit(hotkeys.get("capture_region", "<Ctrl>Print"))
        capture_form.addRow("Capture Region:", self._hk_region)

        self._hk_window = HotkeyEdit(hotkeys.get("capture_window", "<Alt>Print"))
        capture_form.addRow("Capture Window:", self._hk_window)

        capture_group.setLayout(capture_form)
        layout.addWidget(capture_group)

        # Recording hotkeys
        rec_group = QGroupBox("Recording Hotkeys")
        rec_form = QFormLayout()

        self._hk_record = HotkeyEdit(hotkeys.get("start_recording", "<Ctrl><Shift>Print"))
        rec_form.addRow("Start/Stop Recording:", self._hk_record)

        self._hk_gif = HotkeyEdit(hotkeys.get("start_gif", "<Ctrl><Alt>Print"))
        rec_form.addRow("Start/Stop GIF:", self._hk_gif)

        rec_group.setLayout(rec_form)
        layout.addWidget(rec_group)

        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setStyleSheet("color: #f88; padding: 6px;")
        reset_btn.clicked.connect(self._reset_defaults)
        layout.addWidget(reset_btn)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self):
        """Save hotkey configuration."""
        self._config.set("hotkeys.capture_fullscreen", self._hk_fullscreen.hotkey)
        self._config.set("hotkeys.capture_region", self._hk_region.hotkey)
        self._config.set("hotkeys.capture_window", self._hk_window.hotkey)
        self._config.set("hotkeys.start_recording", self._hk_record.hotkey)
        self._config.set("hotkeys.start_gif", self._hk_gif.hotkey)
        self._config.save()
        self.accept()

    def _reset_defaults(self):
        """Reset hotkeys to defaults."""
        self._hk_fullscreen._hotkey = "Print"
        self._hk_fullscreen.setText(HotkeyEdit._format_display("Print"))

        self._hk_region._hotkey = "<Ctrl>Print"
        self._hk_region.setText(HotkeyEdit._format_display("<Ctrl>Print"))

        self._hk_window._hotkey = "<Alt>Print"
        self._hk_window.setText(HotkeyEdit._format_display("<Alt>Print"))

        self._hk_record._hotkey = "<Ctrl><Shift>Print"
        self._hk_record.setText(HotkeyEdit._format_display("<Ctrl><Shift>Print"))

        self._hk_gif._hotkey = "<Ctrl><Alt>Print"
        self._hk_gif.setText(HotkeyEdit._format_display("<Ctrl><Alt>Print"))
