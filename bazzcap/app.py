
import sys
import os
import subprocess
from functools import partial

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QStatusBar, QGroupBox,
    QGridLayout, QSizePolicy, QMessageBox, QFileDialog,
    QDialog, QFormLayout, QLineEdit, QCheckBox, QSpinBox,
    QComboBox, QDialogButtonBox, QScrollArea, QFrame,
    QToolButton, QSplitter,
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, pyqtSignal, QThread, pyqtSlot, QObject,
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QAction, QFont, QColor, QPainter, QPen,
    QBrush, QImage, QKeySequence, QGuiApplication,
)

from bazzcap.config import Config
from bazzcap.overlay import RegionCaptureOverlay, grab_screenshot_via_portal
from bazzcap.clipboard import copy_image_to_clipboard
from bazzcap.history import HistoryManager, HistoryEntry
from bazzcap.hotkeys import HotkeyManager
from bazzcap.hotkey_settings import HotkeySettingsDialog


class SettingsDialog(QDialog):

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("BazzCap — Settings")
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        general = QGroupBox("General")
        form = QFormLayout()

        self._save_dir = QLineEdit(self._config.get("save_directory", ""))
        browse_btn = QToolButton()
        browse_btn.setText("...")
        browse_btn.clicked.connect(self._browse_dir)
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self._save_dir)
        dir_layout.addWidget(browse_btn)
        form.addRow("Save directory:", dir_layout)

        self._filename = QLineEdit(self._config.get("filename_pattern", ""))
        form.addRow("Filename pattern:", self._filename)

        self._auto_copy = QCheckBox("Automatically copy capture to clipboard")
        self._auto_copy.setChecked(self._config.get("auto_copy_to_clipboard", True))
        form.addRow(self._auto_copy)

        self._open_editor = QCheckBox("Open annotation editor after capture")
        self._open_editor.setChecked(self._config.get("open_editor_after_capture", True))
        form.addRow(self._open_editor)

        self._show_magnifier = QCheckBox("Show magnifier during region capture")
        self._show_magnifier.setChecked(self._config.get("show_magnifier", True))
        form.addRow(self._show_magnifier)

        self._format = QComboBox()
        self._format.addItems(["png", "jpg", "bmp", "webp"])
        self._format.setCurrentText(self._config.get("image_format", "png"))
        form.addRow("Image format:", self._format)

        self._minimize_tray = QCheckBox("Minimize to system tray on close")
        self._minimize_tray.setChecked(self._config.get("minimize_to_tray", True))
        form.addRow(self._minimize_tray)

        self._start_with_system = QCheckBox("Start with system (autostart on login)")
        self._start_with_system.setChecked(self._is_autostart_enabled())
        form.addRow(self._start_with_system)

        general.setLayout(form)
        layout.addWidget(general)

        editor = QGroupBox("Annotation Editor")
        ed_form = QFormLayout()

        self._line_width = QSpinBox()
        self._line_width.setRange(1, 30)
        self._line_width.setValue(self._config.get("editor.default_line_width", 3))
        ed_form.addRow("Line width:", self._line_width)

        self._font_size = QSpinBox()
        self._font_size.setRange(8, 72)
        self._font_size.setValue(self._config.get("editor.default_font_size", 16))
        ed_form.addRow("Font size:", self._font_size)

        self._blur_radius = QSpinBox()
        self._blur_radius.setRange(5, 50)
        self._blur_radius.setValue(self._config.get("editor.blur_radius", 15))
        ed_form.addRow("Blur intensity:", self._blur_radius)

        editor.setLayout(ed_form)
        layout.addWidget(editor)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Save Directory", self._save_dir.text())
        if d:
            self._save_dir.setText(d)

    def _save(self):
        self._config.set("save_directory", self._save_dir.text())
        self._config.set("filename_pattern", self._filename.text())
        self._config.set("auto_copy_to_clipboard", self._auto_copy.isChecked())
        self._config.set("open_editor_after_capture", self._open_editor.isChecked())
        self._config.set("show_magnifier", self._show_magnifier.isChecked())
        self._config.set("image_format", self._format.currentText())
        self._config.set("minimize_to_tray", self._minimize_tray.isChecked())
        self._config.set("start_with_system", self._start_with_system.isChecked())
        self._set_autostart(self._start_with_system.isChecked())
        self._config.set("editor.default_line_width", self._line_width.value())
        self._config.set("editor.default_font_size", self._font_size.value())
        self._config.set("editor.blur_radius", self._blur_radius.value())
        self._config.save()
        self.accept()

    _AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
    _AUTOSTART_FILE = os.path.join(_AUTOSTART_DIR, "bazzcap.desktop")
    _BIN_PATH = os.path.expanduser("~/.local/bin/bazzcap")

    def _is_autostart_enabled(self) -> bool:
        return os.path.isfile(self._AUTOSTART_FILE)

    def _set_autostart(self, enabled: bool):
        if enabled:
            os.makedirs(self._AUTOSTART_DIR, exist_ok=True)
            entry = (
                "[Desktop Entry]\n"
                "Name=BazzCap\n"
                "Comment=Screenshot Tool\n"
                f"Exec={self._BIN_PATH}\n"
                "Icon=bazzcap\n"
                "Terminal=false\n"
                "Type=Application\n"
                "X-GNOME-Autostart-enabled=true\n"
                "Hidden=false\n"
            )
            with open(self._AUTOSTART_FILE, "w") as f:
                f.write(entry)
            os.chmod(self._AUTOSTART_FILE, 0o755)
        else:
            if os.path.isfile(self._AUTOSTART_FILE):
                os.remove(self._AUTOSTART_FILE)


class MainWindow(QMainWindow):

    capture_requested = pyqtSignal(str)

    def __init__(self, config: Config, history: HistoryManager, parent=None):
        super().__init__(parent)
        self._config = config
        self._history = history
        self._editor_windows = []
        self._overlay = None

        self.setWindowTitle("BazzCap")
        self.setMinimumSize(750, 550)
        self._apply_dark_theme()
        self._build_ui()
        self._refresh_history()

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #45475a;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                padding: 2px 8px;
                color: #89b4fa;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 10px 18px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45475a;
                border-color: #89b4fa;
            }
            QPushButton:pressed {
                background-color: #585b70;
            }
            QListWidget {
                background-color: #181825;
                border: 1px solid #45475a;
                border-radius: 4px;
                color: #cdd6f4;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #313244;
            }
            QListWidget::item:hover {
                background-color: #313244;
            }
            QListWidget::item:selected {
                background-color: #45475a;
            }
            QStatusBar {
                background-color: #181825;
                color: #6c7086;
                font-size: 11px;
            }
            QLabel {
                color: #cdd6f4;
            }
        """)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 8)

        header_layout = QHBoxLayout()

        title_layout = QVBoxLayout()
        header = QLabel("BazzCap")
        header.setFont(QFont("Sans", 24, QFont.Weight.Bold))
        header.setStyleSheet("color: #89b4fa;")
        title_layout.addWidget(header)

        subtitle = QLabel("Screenshot Tool for Linux")
        subtitle.setStyleSheet("color: #6c7086; font-size: 12px;")
        title_layout.addWidget(subtitle)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        btn_settings = QPushButton("Settings")
        btn_settings.setFixedHeight(36)
        btn_settings.clicked.connect(lambda: self._show_settings())
        header_layout.addWidget(btn_settings)

        btn_hotkeys = QPushButton("Hotkeys")
        btn_hotkeys.setFixedHeight(36)
        btn_hotkeys.clicked.connect(lambda: self._show_hotkey_settings())
        header_layout.addWidget(btn_hotkeys)

        layout.addLayout(header_layout)

        capture_group = QGroupBox("Capture")
        capture_layout = QGridLayout()
        capture_layout.setSpacing(8)

        btn_fullscreen = QPushButton("Fullscreen Screenshot")
        btn_fullscreen.setMinimumHeight(50)
        btn_fullscreen.setToolTip(self._hotkey_tip("capture_fullscreen"))
        btn_fullscreen.clicked.connect(
            lambda: self._start_capture("fullscreen")
        )
        capture_layout.addWidget(btn_fullscreen, 0, 0)

        btn_region = QPushButton("Region Capture")
        btn_region.setMinimumHeight(50)
        btn_region.setToolTip(self._hotkey_tip("capture_region"))
        btn_region.clicked.connect(
            lambda: self._start_capture("region")
        )
        capture_layout.addWidget(btn_region, 0, 1)

        btn_window = QPushButton("Window Capture")
        btn_window.setMinimumHeight(50)
        btn_window.setToolTip(self._hotkey_tip("capture_window"))
        btn_window.clicked.connect(
            lambda: self._start_capture("window")
        )
        capture_layout.addWidget(btn_window, 0, 2)

        capture_group.setLayout(capture_layout)
        layout.addWidget(capture_group)

        history_group = QGroupBox("Recent Captures")
        hist_layout = QVBoxLayout()

        self._history_list = QListWidget()
        self._history_list.setMinimumHeight(160)
        self._history_list.itemDoubleClicked.connect(self._open_history_item)
        hist_layout.addWidget(self._history_list)

        hist_buttons = QHBoxLayout()

        btn_open_dir = QPushButton("Open Folder")
        btn_open_dir.setFixedHeight(34)
        btn_open_dir.clicked.connect(self._open_save_dir)
        hist_buttons.addWidget(btn_open_dir)

        btn_clear_hist = QPushButton("Clear History")
        btn_clear_hist.setFixedHeight(34)
        btn_clear_hist.clicked.connect(self._clear_history)
        hist_buttons.addWidget(btn_clear_hist)

        hist_buttons.addStretch()

        hist_layout.addLayout(hist_buttons)
        history_group.setLayout(hist_layout)
        layout.addWidget(history_group)

        self._status = QStatusBar()
        self.setStatusBar(self._status)

        from bazzcap.capture import detect_available_backends
        backends = detect_available_backends()
        self._status.showMessage(
            f"Ready  |  Backends: {', '.join(backends) if backends else 'XDG Portal'}"
        )

    def _hotkey_tip(self, name: str) -> str:
        hotkeys = self._config.get("hotkeys", {})
        hk = hotkeys.get(name, "")
        if hk:
            display = hk.replace("<Ctrl>", "Ctrl+").replace(
                "<Shift>", "Shift+").replace("<Alt>", "Alt+").replace(
                "<Super>", "Super+")
            return f"Hotkey: {display}"
        return "No hotkey configured"

    def _start_capture(self, mode: str, cursor_pos=None):
        self._was_visible = self.isVisible()
        self.hide()
        QApplication.processEvents()

        QTimer.singleShot(250, lambda: self._do_overlay_capture(mode, cursor_pos))

    def _do_overlay_capture(self, mode: str, cursor_pos=None):
        self._status.showMessage("Grabbing screen...")

        screenshot = grab_screenshot_via_portal()

        if screenshot is None or screenshot.isNull():
            self._status.showMessage("Failed to grab screen!")
            self.show()
            self._notify("Capture failed", "Could not grab screen")
            return

        overlay_mode = {
            "fullscreen": RegionCaptureOverlay.MODE_FULLSCREEN,
            "region": RegionCaptureOverlay.MODE_REGION,
            "window": RegionCaptureOverlay.MODE_REGION,
        }.get(mode, RegionCaptureOverlay.MODE_REGION)

        self._overlay = RegionCaptureOverlay(screenshot, overlay_mode,
                                              cursor_pos=cursor_pos)
        self._overlay.capture_completed.connect(self._on_overlay_captured)
        self._overlay.capture_cancelled.connect(self._on_overlay_cancelled)

        target = self._overlay._target_screen
        if target:
            self._overlay.winId()
            if self._overlay.windowHandle():
                self._overlay.windowHandle().setScreen(target)
        self._overlay.showFullScreen()

    def _on_overlay_captured(self, pixmap: QPixmap):
        if self._overlay:
            self._overlay.close()
            self._overlay.deleteLater()
            self._overlay = None

        if pixmap.isNull():
            if getattr(self, '_was_visible', False):
                self.show()
            return

        path = self._config.generate_filepath()
        ext = self._config.get("image_format", "png").upper()
        quality = 95 if ext in ("JPG", "JPEG") else -1
        pixmap.save(path, ext, quality)

        if os.path.isfile(path):
            entry = HistoryEntry.create(path, "screenshot", "region")
            self._history.add(entry)
            self._refresh_history()

            copy_image_to_clipboard(path)

            self._notify("Screenshot saved & copied",
                         os.path.basename(path))

            self._status.showMessage(f"Saved: {path}")
        else:
            self._status.showMessage("Failed to save capture!")

        if getattr(self, '_was_visible', False):
            self.show()

    def _on_overlay_cancelled(self):
        if self._overlay:
            self._overlay.close()
            self._overlay.deleteLater()
            self._overlay = None
        if getattr(self, '_was_visible', False):
            self.show()
        self._status.showMessage("Capture cancelled")

    def _open_editor(self, path: str):
        try:
            from bazzcap.editor import AnnotationEditor
            editor = AnnotationEditor(path, self._config)
            editor.image_saved.connect(self._on_editor_saved)
            editor.show()
            self._editor_windows.append(editor)
        except Exception as e:
            self._status.showMessage(f"Editor error: {e}")
            self.show()

    def _on_editor_saved(self, path: str):
        if self._config.get("auto_copy_to_clipboard", True):
            copy_image_to_clipboard(path)
        self.show()

    def _refresh_history(self):
        self._history_list.clear()
        for entry in self._history.entries[:50]:
            icon = {"screenshot": "IMG"}.get(entry.capture_type, "FILE")
            name = os.path.basename(entry.filepath)
            size_kb = entry.file_size / 1024
            ts = entry.timestamp[:19].replace("T", "  ")
            text = f"  [{icon}]  {name}    ({size_kb:.0f} KB)    {ts}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry.filepath)
            self._history_list.addItem(item)

    def _open_history_item(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path or not os.path.isfile(path):
            self._status.showMessage("File not found!")
            return

        ext = os.path.splitext(path)[1].lower()
        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
            self._open_editor(path)
        else:
            subprocess.Popen(["xdg-open", path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _open_save_dir(self):
        subprocess.Popen(["xdg-open", self._config.save_directory],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _clear_history(self):
        self._history.clear()
        self._refresh_history()

    def _show_settings(self):
        dialog = SettingsDialog(self._config, self)
        dialog.exec()

    def _show_hotkey_settings(self):
        dialog = HotkeySettingsDialog(self._config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            app_obj = QApplication.instance()
            if hasattr(app_obj, '_bazzcap_app') and hasattr(app_obj._bazzcap_app, '_reregister_hotkeys'):
                app_obj._bazzcap_app._reregister_hotkeys()
            self._status.showMessage("Hotkeys updated and applied!")

    def _notify(self, title: str, message: str):
        try:
            subprocess.Popen(
                ["notify-send", "-a", "BazzCap", "-i", "camera-photo",
                 title, message],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except (OSError, FileNotFoundError):
            pass

    def closeEvent(self, event):
        if self._config.get("minimize_to_tray", True):
            event.ignore()
            self.hide()
        else:
            event.accept()


class SystemTray(QSystemTrayIcon):

    capture_requested = pyqtSignal(str)
    show_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    hotkey_settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._create_icon()
        self.setToolTip("BazzCap")
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _create_icon(self):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(137, 180, 250)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(1, 1, 30, 30)
        painter.setPen(QPen(QColor(30, 30, 46)))
        font = QFont("Sans", 16, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "B")
        painter.end()
        self.setIcon(QIcon(pixmap))

    def _build_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #45475a;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #45475a;
            }
            QMenu::separator {
                height: 1px;
                background: #45475a;
                margin: 4px 8px;
            }
        """)

        menu.addAction("Fullscreen", lambda: self.capture_requested.emit("fullscreen"))
        menu.addAction("Region Capture", lambda: self.capture_requested.emit("region"))
        menu.addAction("Window Capture", lambda: self.capture_requested.emit("window"))
        menu.addSeparator()
        menu.addAction("Show BazzCap", lambda: self.show_requested.emit())
        menu.addAction("Settings", lambda: self.settings_requested.emit())
        menu.addAction("Hotkeys", lambda: self.hotkey_settings_requested.emit())
        menu.addSeparator()
        menu.addAction("Quit", lambda: self.quit_requested.emit())

        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_requested.emit()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            pass
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            self.capture_requested.emit("region")


class _HotkeyBridge(QObject):
    trigger = pyqtSignal(str, object)


class BazzCapApp:

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("BazzCap")
        self.app.setQuitOnLastWindowClosed(False)

        self.config = Config()
        self.history = HistoryManager()
        self.hotkey_manager = HotkeyManager()

        self._hotkey_bridge = _HotkeyBridge()
        self._hotkey_bridge.trigger.connect(
            lambda name, pos: self._on_hotkey_triggered(name, pos)
        )

        self.main_window = MainWindow(self.config, self.history)
        self.tray = SystemTray()

        self.tray.capture_requested.connect(self._tray_capture)
        self.tray.show_requested.connect(self._show_window)
        self.tray.settings_requested.connect(self.main_window._show_settings)
        self.tray.hotkey_settings_requested.connect(self.main_window._show_hotkey_settings)
        self.tray.quit_requested.connect(self._quit)

        self.tray.show()
        self._setup_hotkeys()

        self.app._bazzcap_app = self

    def _reregister_hotkeys(self):
        hotkeys = self.config.get("hotkeys", {})
        new_bindings = {}
        for name in ["capture_fullscreen", "capture_region", "capture_window"]:
            combo = hotkeys.get(name, "")
            if combo:
                new_bindings[name] = combo
        self.hotkey_manager.reregister(new_bindings)

    def _setup_hotkeys(self):
        hotkeys = self.config.get("hotkeys", {})

        all_names = [
            "capture_fullscreen", "capture_region", "capture_window",
        ]

        for name in all_names:
            combo = hotkeys.get(name, "")
            if combo:
                def make_callback(n):
                    return lambda cursor_pos=None: self._hotkey_bridge.trigger.emit(n, cursor_pos)
                self.hotkey_manager.register(name, combo, make_callback(name))

        try:
            self.hotkey_manager.start()
        except Exception:
            pass

    def _on_hotkey_triggered(self, name: str, cursor_pos=None):
        action_map = {
            "capture_fullscreen": lambda: self.main_window._start_capture("fullscreen", cursor_pos),
            "capture_region": lambda: self.main_window._start_capture("region", cursor_pos),
            "capture_window": lambda: self.main_window._start_capture("window", cursor_pos),
        }
        action = action_map.get(name)
        if action:
            action()

    def _tray_capture(self, mode: str):
        self.main_window._start_capture(mode)

    def _show_window(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _quit(self):
        self.hotkey_manager.stop()
        self.tray.hide()
        self.app.quit()

    def run(self) -> int:
        if not self.config.get("start_minimized", False):
            self.main_window.show()
        return self.app.exec()
