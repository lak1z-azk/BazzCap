
import sys
import os
import shutil
import subprocess
import logging
import fcntl
import shlex
from functools import partial

IS_MACOS = sys.platform == "darwin"
AUTOSTART_ENV_FLAG = "BAZZCAP_AUTOSTART"

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
    Qt, QTimer, QSize, pyqtSignal, QThread, pyqtSlot, QObject, QUrl,
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QAction, QFont, QColor, QPainter, QPen,
    QBrush, QImage, QKeySequence, QGuiApplication, QDesktopServices,
)

from bazzcap.config import Config
from bazzcap.overlay import RegionCaptureOverlay, grab_screenshot_via_portal
from bazzcap.capture import (
    capture_fullscreen as _capture_fullscreen_to_file,
    capture_window as _capture_window_to_file,
)
from bazzcap.runtime import is_flatpak, is_frozen_bundle, external_command_env
from bazzcap.clipboard import copy_image_to_clipboard
from bazzcap.history import HistoryManager, HistoryEntry
from bazzcap.hotkeys import HotkeyManager
from bazzcap.hotkey_settings import HotkeySettingsDialog
from bazzcap.logging_utils import setup_logging, install_global_exception_handlers


logger = logging.getLogger(__name__)


def _fallback_app_icon() -> QIcon:
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
    return QIcon(pixmap)


def load_app_icon() -> QIcon:
    """Load the bundled BazzCap icon with safe fallbacks."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Prefer PNG for compatibility (tray icons on Wayland/GNOME need bitmap)
    candidates = [
        os.path.join(base_dir, "resources", "bazzcap.png"),
        os.path.join(base_dir, "resources", "bazzcap.svg"),
        os.path.join(os.path.dirname(base_dir), "bazzcap", "resources", "bazzcap.png"),
        os.path.join(os.path.dirname(base_dir), "bazzcap", "resources", "bazzcap.svg"),
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "bazzcap.png"),
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "bazzcap.svg"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            icon = QIcon(path)
            if not icon.isNull():
                return icon

    themed = QIcon.fromTheme("bazzcap")
    if not themed.isNull():
        return themed

    return _fallback_app_icon()


class _FullscreenPicker(QWidget):
    """Lightweight transparent click-catcher for fullscreen capture.

    Shows the screenshot as background on the target screen.
    One click = capture that screen.  Right-click or Escape = cancel.
    No toolbar, no dimming, no editor.
    """

    screen_picked = pyqtSignal(object, QPixmap)   # (QScreen, cropped pixmap)
    pick_cancelled = pyqtSignal()

    def __init__(self, screenshot: QPixmap, screen):
        super().__init__()
        self._screen = screen
        self._active = True
        geo = screen.geometry()
        self._cropped = screenshot.copy(geo.x(), geo.y(),
                                        geo.width(), geo.height())
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.drawPixmap(0, 0, self._cropped)
        # Subtle border highlight so user knows it's clickable
        p.setPen(QPen(QColor(137, 180, 250, 120), 4))
        p.drawRect(self.rect().adjusted(2, 2, -2, -2))
        p.end()

    def mousePressEvent(self, event):
        if not self._active:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._active = False
            self.screen_picked.emit(self._screen, self._cropped)
        elif event.button() == Qt.MouseButton.RightButton:
            self._active = False
            self.pick_cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._active = False
            self.pick_cancelled.emit()

    def deactivate(self):
        self._active = False
        self.hide()
        self.close()
        self.deleteLater()


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

    if IS_MACOS:
        _AUTOSTART_DIR = os.path.expanduser("~/Library/LaunchAgents")
        _AUTOSTART_FILE = os.path.join(_AUTOSTART_DIR, "com.bazzcap.plist")
        _BIN_PATH = "/usr/local/bin/bazzcap"
    else:
        _AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
        _AUTOSTART_FILE = os.path.join(_AUTOSTART_DIR, "bazzcap.desktop")
        _BIN_PATH = os.path.expanduser("~/.local/bin/bazzcap")

    def _is_autostart_enabled(self) -> bool:
        return os.path.isfile(self._AUTOSTART_FILE)

    @staticmethod
    def _source_entrypoint() -> str:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "bazzcap.py"))

    def _launch_command(self) -> list[str]:
        if os.path.isfile(self._BIN_PATH) and os.access(self._BIN_PATH, os.X_OK):
            return [self._BIN_PATH]
        if is_frozen_bundle():
            return [sys.executable]
        return [sys.executable, self._source_entrypoint()]

    def _set_autostart(self, enabled: bool):
        if enabled:
            os.makedirs(self._AUTOSTART_DIR, exist_ok=True)
            cmd_parts = self._launch_command()
            if IS_MACOS:
                plist = (
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"'
                    ' "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                    '<plist version="1.0">\n<dict>\n'
                    '  <key>Label</key>\n  <string>com.bazzcap</string>\n'
                    '  <key>ProgramArguments</key>\n  <array>\n'
                    + "".join(f'    <string>{shlex.quote(p)}</string>\n'
                               for p in cmd_parts)
                    + '  </array>\n'
                    '  <key>RunAtLoad</key>\n  <true/>\n'
                    '</dict>\n</plist>\n'
                )
                with open(self._AUTOSTART_FILE, "w") as f:
                    f.write(plist)
            else:
                exec_str = " ".join(shlex.quote(p) for p in cmd_parts)
                entry = (
                    "[Desktop Entry]\n"
                    "Name=BazzCap\n"
                    "Comment=Screenshot Tool\n"
                    f"Exec=env {AUTOSTART_ENV_FLAG}=1 {exec_str}\n"
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


# ---------------------------------------------------------------------------
# Background workers — keep blocking subprocess work off the Qt main thread
# ---------------------------------------------------------------------------

def _mute_event_sounds():
    """Temporarily disable GNOME event sounds. Returns previous value."""
    if IS_MACOS:
        return None
    try:
        r = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.sound", "event-sounds"],
            capture_output=True, text=True, timeout=3,
            env=external_command_env(),
        )
        was_on = "true" in (r.stdout or "").lower()
        if was_on:
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.sound",
                 "event-sounds", "false"],
                capture_output=True, timeout=3,
                env=external_command_env(),
            )
        return was_on
    except (subprocess.SubprocessError, OSError):
        return None


def _restore_event_sounds(was_on):
    """Restore GNOME event sounds to previous state."""
    if IS_MACOS:
        return
    if was_on:
        try:
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.sound",
                 "event-sounds", "true"],
                capture_output=True, timeout=3,
                env=external_command_env(),
            )
        except (subprocess.SubprocessError, OSError):
            pass


class _ScreenshotWorker(QThread):
    """Run screenshot capture off the Qt main thread (prefers grim)."""
    finished = pyqtSignal(object)

    def run(self):
        pixmap = None
        try:
            pixmap = grab_screenshot_via_portal(allow_screen_grab=False)
        except Exception:
            logger.exception("Screenshot worker failed")
        self.finished.emit(pixmap)


class _ScreenPickerOverlay(QWidget):
    """Fullscreen overlay on one monitor — click to select that screen."""
    screen_selected = pyqtSignal(object)   # emits QScreen
    cancelled = pyqtSignal()

    def __init__(self, screenshot: QPixmap, target_screen, parent=None):
        super().__init__(parent)
        self._target_screen = target_screen
        geo = target_screen.geometry()
        vgeo = QGuiApplication.primaryScreen().virtualGeometry()
        x = geo.x() - vgeo.x()
        y = geo.y() - vgeo.y()
        self._crop = screenshot.copy(x, y, geo.width(), geo.height())
        self._dimmed = self._crop.copy()
        p = QPainter(self._dimmed)
        p.fillRect(self._dimmed.rect(), QColor(0, 0, 0, 120))
        p.end()
        self._hovered = False
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

    def paintEvent(self, event):
        p = QPainter(self)
        if self._hovered:
            p.drawPixmap(0, 0, self._crop)
            pen = QPen(QColor(0, 255, 100), 4)
            p.setPen(pen)
            p.drawRect(2, 2, self.width() - 4, self.height() - 4)
        else:
            p.drawPixmap(0, 0, self._dimmed)
        font = QFont("monospace", 18, QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QColor(0, 255, 100) if self._hovered else QColor(180, 180, 180))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                   "Click to capture" if self._hovered else "")
        p.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.screen_selected.emit(self._target_screen)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()

class _WindowCaptureWorker(QThread):
    """Run window capture off the Qt main thread."""
    finished = pyqtSignal(bool, str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self):
        try:
            ok = _capture_window_to_file(self._path)
        except Exception:
            logger.exception("Window capture worker failed")
            ok = False
        self.finished.emit(ok, self._path)


class _FullscreenCaptureWorker(QThread):
    """Run fullscreen capture backend off the Qt main thread."""
    finished = pyqtSignal(bool, str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self):
        try:
            ok = _capture_fullscreen_to_file(self._path)
        except Exception:
            logger.exception("Fullscreen capture worker failed")
            ok = False
        self.finished.emit(ok, self._path)


class MainWindow(QMainWindow):

    capture_requested = pyqtSignal(str)

    def __init__(self, config: Config, history: HistoryManager, app_icon: QIcon | None = None, parent=None):
        super().__init__(parent)
        self._config = config
        self._history = history
        self._editor_windows = []
        self._overlay = None
        self._overlays = []
        self._tray_available = True
        self._capture_in_progress = False
        self._pending_capture_cursor = None
        self._screenshot_worker = None
        self._window_capture_worker = None
        self._clipboard_only = False
        self._ocr_mode = False

        self.setWindowTitle("BazzCap")
        if app_icon is not None and not app_icon.isNull():
            self.setWindowIcon(app_icon)
        self.setMinimumSize(560, 420)
        self._apply_dark_theme()
        self._build_ui()
        self._refresh_history()

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #090d0a;
                color: #b8ffcf;
            }
            QWidget#rootPanel {
                background-color: #090d0a;
            }
            QScrollArea {
                border: none;
                background-color: #090d0a;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #090d0a;
            }
            QFrame#surfacePanel {
                background-color: #0d1510;
                border: 1px solid #1d3a27;
                border-radius: 10px;
            }
            QFrame#divider {
                background-color: #17301f;
                min-height: 1px;
                max-height: 1px;
                border: none;
            }
            QSplitter::handle {
                background-color: #17301f;
                width: 1px;
            }
            QPushButton {
                background-color: #112017;
                color: #b8ffcf;
                border: 1px solid #235130;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 500;
                font-family: Monospace;
            }
            QPushButton:hover {
                background-color: #163021;
                border-color: #2f7143;
            }
            QPushButton:pressed {
                background-color: #0d1a13;
            }
            QPushButton#primaryAction {
                background-color: #112017;
                color: #b8ffcf;
                border: 1px solid #235130;
                font-weight: 500;
            }
            QPushButton#primaryAction:hover {
                background-color: #163021;
            }
            QPushButton#secondaryAction {
                min-height: 30px;
            }
            QPushButton#toolbarButton {
                min-width: 72px;
                padding: 4px 8px;
            }
            QListWidget {
                background-color: #0a120d;
                border: 1px solid #1d3a27;
                border-radius: 8px;
                color: #c7ffd8;
                font-size: 12px;
                outline: 0;
                padding: 3px;
                font-family: Monospace;
            }
            QListWidget::item {
                padding: 6px 8px;
                border: 1px solid transparent;
                border-radius: 6px;
                margin: 2px 0;
            }
            QListWidget::item:hover {
                background-color: #122217;
                border-color: #235130;
            }
            QListWidget::item:selected {
                background-color: #183024;
                border-color: #2f7143;
            }
            QStatusBar {
                background-color: #080f0a;
                color: #76c48f;
                border-top: 1px solid #17301f;
                font-size: 11px;
                font-family: Monospace;
            }
            QLabel {
                color: #bfffd4;
                border: none;
                background: transparent;
            }
            QLabel#windowEyebrow {
                color: #6ca780;
                font-size: 11px;
                font-family: Monospace;
            }
            QLabel#windowTitle {
                color: #d6ffe3;
                font-size: 16px;
                font-weight: 700;
                font-family: Monospace;
            }
            QLabel#windowSubtitle {
                color: #79bc91;
                font-size: 11px;
                font-family: Monospace;
            }
            QLabel#sectionTitle {
                color: #d6ffe3;
                font-size: 13px;
                font-weight: 700;
                font-family: Monospace;
            }
            QLabel#sectionNote {
                color: #79bc91;
                font-size: 11px;
                font-family: Monospace;
            }
            QLabel#pathLabel {
                color: #9de5b8;
                background-color: #0a120d;
                border: 1px solid #1d3a27;
                border-radius: 8px;
                padding: 6px 8px;
                font-family: Monospace;
            }
            QLabel#microLabel {
                color: #6ca780;
                font-size: 11px;
                font-family: Monospace;
            }
        """)

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setCentralWidget(scroll)

        central = QWidget()
        central.setObjectName("rootPanel")
        central.setMinimumWidth(500)
        scroll.setWidget(central)

        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 6)

        header = QHBoxLayout()
        header.setSpacing(6)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)

        title = QLabel("BazzCap")
        title.setObjectName("windowTitle")
        title_box.addWidget(title)

        subtitle = QLabel("Recent captures")
        subtitle.setObjectName("windowSubtitle")
        title_box.addWidget(subtitle)

        header.addLayout(title_box)
        header.addStretch()

        btn_hotkeys = QPushButton("Hotkeys")
        btn_hotkeys.setObjectName("toolbarButton")
        btn_hotkeys.setFixedHeight(26)
        btn_hotkeys.setMinimumWidth(74)
        btn_hotkeys.clicked.connect(lambda: self._show_hotkey_settings())
        header.addWidget(btn_hotkeys)

        btn_settings = QPushButton("Settings")
        btn_settings.setObjectName("toolbarButton")
        btn_settings.setFixedHeight(26)
        btn_settings.setMinimumWidth(74)
        btn_settings.clicked.connect(lambda: self._show_settings())
        header.addWidget(btn_settings)

        layout.addLayout(header)

        right_panel = QFrame()
        right_panel.setObjectName("surfacePanel")
        right_panel.setMinimumWidth(460)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(8)
        right_layout.setContentsMargins(10, 10, 10, 10)

        history_header = QHBoxLayout()
        history_header.setSpacing(6)

        history_title = QLabel("Recent Captures")
        history_title.setObjectName("sectionTitle")
        history_header.addWidget(history_title)
        history_header.addStretch()

        btn_open_dir = QPushButton("Open Folder")
        btn_open_dir.setObjectName("toolbarButton")
        btn_open_dir.setFixedHeight(26)
        btn_open_dir.setMinimumWidth(86)
        btn_open_dir.clicked.connect(self._open_save_dir)
        history_header.addWidget(btn_open_dir)

        btn_clear_hist = QPushButton("Clear History")
        btn_clear_hist.setObjectName("toolbarButton")
        btn_clear_hist.setFixedHeight(26)
        btn_clear_hist.setMinimumWidth(86)
        btn_clear_hist.clicked.connect(self._clear_history)
        history_header.addWidget(btn_clear_hist)

        right_layout.addLayout(history_header)

        self._history_list = QListWidget()
        self._history_list.setMinimumHeight(200)
        self._history_list.itemDoubleClicked.connect(self._open_history_item)
        self._history_list.itemSelectionChanged.connect(self._sync_history_actions)
        self._history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._history_list.customContextMenuRequested.connect(self._show_history_context_menu)
        right_layout.addWidget(self._history_list)

        history_actions = QHBoxLayout()
        history_actions.setSpacing(6)

        self._btn_edit_history = QPushButton("Edit")
        self._btn_edit_history.setObjectName("toolbarButton")
        self._btn_edit_history.setFixedHeight(26)
        self._btn_edit_history.setMinimumWidth(60)
        self._btn_edit_history.setEnabled(False)
        self._btn_edit_history.clicked.connect(self._edit_selected_history_item)
        history_actions.addWidget(self._btn_edit_history)

        self._btn_delete_history = QPushButton("Delete")
        self._btn_delete_history.setObjectName("toolbarButton")
        self._btn_delete_history.setFixedHeight(26)
        self._btn_delete_history.setMinimumWidth(60)
        self._btn_delete_history.setEnabled(False)
        self._btn_delete_history.clicked.connect(self._delete_selected_history_item)
        history_actions.addWidget(self._btn_delete_history)

        history_actions.addStretch()

        self._btn_remove_missing = QPushButton("Remove Missing")
        self._btn_remove_missing.setObjectName("toolbarButton")
        self._btn_remove_missing.setFixedHeight(26)
        self._btn_remove_missing.setMinimumWidth(104)
        self._btn_remove_missing.clicked.connect(self._remove_missing_history_items)
        history_actions.addWidget(self._btn_remove_missing)

        right_layout.addLayout(history_actions)
        layout.addWidget(right_panel)

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

    def _start_capture(self, mode: str, cursor_pos=None, clipboard_only: bool = False):
        logger.info("Capture requested: mode=%s cursor_pos=%s clipboard_only=%s",
                    mode, cursor_pos, clipboard_only)
        if self._capture_in_progress:
            logger.info("Capture request ignored; previous capture still in progress")
            return
        self._capture_in_progress = True
        self._pending_capture_cursor = cursor_pos
        self._clipboard_only = clipboard_only
        self._was_visible = self.isVisible()
        self.hide()
        QApplication.processEvents()

        if mode == "ocr":
            self._ocr_mode = True
            QTimer.singleShot(250, lambda: self._do_overlay_capture("region"))
        elif mode == "fullscreen":
            QTimer.singleShot(250, self._do_fullscreen_capture)
        elif mode == "window":
            QTimer.singleShot(250, self._do_window_capture)
        else:
            QTimer.singleShot(250, lambda: self._do_overlay_capture(mode))

    @staticmethod
    def _mute_event_sounds():
        return _mute_event_sounds()

    @staticmethod
    def _restore_event_sounds(was_on):
        _restore_event_sounds(was_on)

    def _stop_screenshot_worker(self):
        """Safely terminate any running screenshot worker thread."""
        worker = getattr(self, '_screenshot_worker', None)
        if worker is not None:
            try:
                worker.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            if worker.isRunning():
                worker.quit()
                worker.wait(3000)
                if worker.isRunning():
                    worker.terminate()
                    worker.wait(2000)
            worker.deleteLater()
        self._screenshot_worker = None

    def _cleanup_screenshot_worker(self):
        """Release a screenshot worker that has already finished."""
        worker = getattr(self, '_screenshot_worker', None)
        if worker is not None:
            worker.deleteLater()
        self._screenshot_worker = None

    def _do_fullscreen_capture(self):
        """Capture fullscreen using BazzCap snapshot, no flashing overlays."""
        try:
            logger.info("Starting fullscreen screenshot worker")
            self._status.showMessage("Capturing screen...")
            self._stop_screenshot_worker()
            self._screenshot_worker = _ScreenshotWorker()
            self._screenshot_worker.finished.connect(
                self._on_fullscreen_screenshot_ready)
            self._screenshot_worker.start()
        except Exception:
            logger.exception("Fullscreen capture crashed")
            self._status.showMessage("Fullscreen capture crashed. Check bazzcap.log")
            self._capture_in_progress = False
            if getattr(self, '_was_visible', False):
                self.show()

    def _on_fullscreen_screenshot_ready(self, screenshot):
        self._cleanup_screenshot_worker()
        try:
            logger.info("Fullscreen screenshot ready: %s",
                        "null" if (screenshot is None or screenshot.isNull()) else
                        f"{screenshot.width()}x{screenshot.height()}")
            if screenshot is None or screenshot.isNull():
                self._status.showMessage("Failed to grab screen!")
                self._notify("Capture failed", "Could not grab screen")
                self._capture_in_progress = False
                if getattr(self, '_was_visible', False):
                    self.show()
                return

            screens = QGuiApplication.screens()

            # Single monitor — capture it directly, no picker needed
            if len(screens) <= 1:
                scr = screens[0] if screens else QGuiApplication.primaryScreen()
                geo = scr.geometry()
                vgeo = QGuiApplication.primaryScreen().virtualGeometry()
                cropped = screenshot.copy(
                    geo.x() - vgeo.x(), geo.y() - vgeo.y(),
                    geo.width(), geo.height())
                if not cropped.isNull():
                    self._save_and_notify(cropped, "fullscreen")
                    return
                self._status.showMessage("Failed to crop screen!")
                self._capture_in_progress = False
                if getattr(self, '_was_visible', False):
                    self.show()
                return

            # Multi-monitor — show screen picker overlays
            self._fullscreen_screenshot = screenshot
            self._screen_pickers = []
            for scr in screens:
                picker = _ScreenPickerOverlay(screenshot, scr)
                picker.screen_selected.connect(self._on_screen_picked)
                picker.cancelled.connect(self._on_screen_picker_cancelled)
                self._screen_pickers.append(picker)

            for picker in self._screen_pickers:
                picker.winId()
                handle = picker.windowHandle()
                if handle is not None:
                    handle.setScreen(picker._target_screen)
                picker.showFullScreen()

        except Exception:
            logger.exception("Fullscreen capture crashed")
            self._status.showMessage("Fullscreen capture crashed. Check bazzcap.log")
            self._capture_in_progress = False
            if getattr(self, '_was_visible', False):
                self.show()

    def _on_screen_picked(self, target_screen):
        """User clicked a screen in the picker — crop and save."""
        logger.info("Screen picked: %s", target_screen.name())
        try:
            for p in getattr(self, '_screen_pickers', []):
                p.hide()
                p.close()
                p.deleteLater()
            self._screen_pickers = []

            screenshot = getattr(self, '_fullscreen_screenshot', None)
            if screenshot is None or screenshot.isNull():
                self._status.showMessage("Screenshot lost!")
                self._capture_in_progress = False
                if getattr(self, '_was_visible', False):
                    self.show()
                return

            geo = target_screen.geometry()
            vgeo = QGuiApplication.primaryScreen().virtualGeometry()
            cropped = screenshot.copy(
                geo.x() - vgeo.x(), geo.y() - vgeo.y(),
                geo.width(), geo.height())
            self._fullscreen_screenshot = None

            if cropped.isNull():
                self._status.showMessage("Failed to crop selected screen!")
                self._capture_in_progress = False
                if getattr(self, '_was_visible', False):
                    self.show()
                return

            self._save_and_notify(cropped, "fullscreen")
        except Exception:
            logger.exception("Screen picker finalize crashed")
            self._status.showMessage("Capture crashed. Check bazzcap.log")
            self._capture_in_progress = False
            if getattr(self, '_was_visible', False):
                self.show()

    def _on_screen_picker_cancelled(self):
        """User pressed Escape in screen picker."""
        for p in getattr(self, '_screen_pickers', []):
            p.hide()
            p.close()
            p.deleteLater()
        self._screen_pickers = []
        self._fullscreen_screenshot = None
        self._capture_in_progress = False
        if getattr(self, '_was_visible', False):
            self.show()
        self._status.showMessage("Capture cancelled")

    def _do_window_capture(self):
        """Capture the focused window — runs in a background thread."""
        try:
            logger.info("Starting window capture worker")
            self._status.showMessage("Capturing window...")
            path = self._config.generate_filepath()
            self._window_capture_worker = _WindowCaptureWorker(path)
            self._window_capture_worker.finished.connect(
                self._on_window_capture_ready)
            self._window_capture_worker.start()
        except Exception:
            logger.exception("Window capture crashed")
            self._status.showMessage("Window capture crashed. Check bazzcap.log")
            if getattr(self, '_was_visible', False):
                self.show()

    def _on_window_capture_ready(self, ok, path):
        if self._window_capture_worker is not None:
            self._window_capture_worker.deleteLater()
            self._window_capture_worker = None
        self._handle_captured_file(ok, path, "window", "Window captured & copied")

    def _handle_captured_file(self, ok, path, capture_type, success_title):
        if getattr(self, '_clipboard_only', False):
            self._clipboard_only = False
            try:
                if ok and os.path.isfile(path):
                    copy_image_to_clipboard(path)
                    self._notify("Screenshot copied to clipboard", "Not saved to disk")
                    self._status.showMessage("Copied to clipboard (not saved)")
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                else:
                    self._status.showMessage(f"{capture_type.capitalize()} capture failed!")
            except Exception:
                logger.exception("%s clipboard-only capture failed", capture_type)
            finally:
                self._capture_in_progress = False
                if getattr(self, '_was_visible', False):
                    self.show()
            return
        try:
            if ok and os.path.isfile(path):
                entry = HistoryEntry.create(path, "screenshot", capture_type)
                self._history.add(entry)
                self._refresh_history()
                copy_image_to_clipboard(path)
                self._notify(success_title, os.path.basename(path))
                self._status.showMessage(f"Saved: {path}")
                if self._config.get("open_editor_after_capture", True):
                    self._open_editor(path)
                    return
            else:
                self._status.showMessage(f"{capture_type.capitalize()} capture failed!")
                self._notify("Capture failed", f"Could not capture {capture_type}")
        except Exception:
            logger.exception("%s capture finalize crashed", capture_type)
            self._status.showMessage(f"{capture_type.capitalize()} capture crashed. Check bazzcap.log")
        finally:
            self._capture_in_progress = False
            if getattr(self, '_was_visible', False):
                self.show()

    @staticmethod
    def _get_cursor_pos():
        from PyQt6.QtGui import QCursor
        pos = QCursor.pos()
        if not pos.isNull():
            return (pos.x(), pos.y())
        if not IS_MACOS:
            import subprocess, re
            try:
                r = subprocess.run(
                    ["xdotool", "getmouselocation"],
                    capture_output=True, text=True, timeout=3,
                )
                m = re.search(r"x:(\d+) y:(\d+)", r.stdout or "")
                if m:
                    return (int(m.group(1)), int(m.group(2)))
            except (subprocess.SubprocessError, OSError, FileNotFoundError):
                pass
        return None

    def _do_overlay_capture(self, mode: str):
        """Region capture using BazzCap overlay UI.

        Try a fast Qt screen grab first; on Wayland sessions where that may
        return null, fall back to the screenshot worker path.
        """
        try:
            logger.info("Starting in-app region overlay capture")
            self._status.showMessage("Grabbing screen...")
            screen = QGuiApplication.primaryScreen()
            screenshot = screen.grabWindow(0) if screen else None

            if screenshot is None or screenshot.isNull():
                logger.warning("Qt screen grab returned null, falling back to screenshot worker")
                self._stop_screenshot_worker()
                self._screenshot_worker = _ScreenshotWorker()
                self._screenshot_worker.finished.connect(self._on_overlay_worker_ready)
                self._screenshot_worker.start()
                return

            self._show_region_overlays(screenshot)
        except Exception:
            logger.exception("Region capture crashed")
            self._status.showMessage("Region capture crashed. Check bazzcap.log")
            if getattr(self, '_was_visible', False):
                self.show()

    def _on_overlay_worker_ready(self, screenshot):
        self._cleanup_screenshot_worker()
        try:
            if screenshot is None or screenshot.isNull():
                self._status.showMessage("Failed to grab screen!")
                self.show()
                self._notify("Capture failed", "Could not grab screen")
                self._capture_in_progress = False
                return

            self._show_region_overlays(screenshot)
        except Exception:
            logger.exception("Region capture crashed")
            self._status.showMessage("Region capture crashed. Check bazzcap.log")
            self._capture_in_progress = False
            if getattr(self, '_was_visible', False):
                self.show()

    def _show_region_overlays(self, screenshot: QPixmap):
        try:
            self._overlays = []
            screens = QGuiApplication.screens()
            show_mag = self._config.get("show_magnifier", True)
            for scr in screens:
                ov = RegionCaptureOverlay(screenshot, RegionCaptureOverlay.MODE_REGION,
                                          screen=scr, show_magnifier=show_mag)
                ov.capture_completed.connect(self._on_overlay_captured)
                ov.capture_cancelled.connect(self._on_overlay_cancelled)
                ov.overlay_activated.connect(self._on_overlay_activated)
                self._overlays.append(ov)

            for ov in self._overlays:
                ov.winId()
                handle = ov.windowHandle()
                if handle is not None:
                    handle.setScreen(ov._target_screen)
                ov.showFullScreen()

            self._overlay = None
        except Exception:
            logger.exception("Region capture crashed")
            self._status.showMessage("Region capture crashed. Check bazzcap.log")
            if getattr(self, '_was_visible', False):
                self.show()

    def _on_overlay_activated(self, active_overlay):
        """One overlay received interaction — close all others."""
        self._overlay = active_overlay
        for ov in self._overlays:
            if ov is not active_overlay:
                ov.deactivate()
        self._overlays = [active_overlay]

    def _save_and_notify(self, pixmap: QPixmap, capture_type: str = "region"):
        """Save a pixmap, add to history, copy to clipboard, and notify."""
        if getattr(self, '_clipboard_only', False):
            self._clipboard_only = False
            self._save_clipboard_only(pixmap)
            return
        try:
            if pixmap.isNull():
                if getattr(self, '_was_visible', False):
                    self.show()
                return

            path = self._config.generate_filepath()
            ext = self._config.get("image_format", "png").upper()
            quality = 95 if ext in ("JPG", "JPEG") else -1
            pixmap.save(path, ext, quality)

            if os.path.isfile(path):
                entry = HistoryEntry.create(path, "screenshot", capture_type)
                self._history.add(entry)
                self._refresh_history()
                copy_image_to_clipboard(path)
                self._notify("Screenshot saved & copied",
                             os.path.basename(path))
                self._status.showMessage(f"Saved: {path}")
                if self._config.get("open_editor_after_capture", True):
                    self._open_editor(path)
                    return  # editor's closeEvent will show the main window
            else:
                self._status.showMessage("Failed to save capture!")
        except Exception:
            logger.exception("Saving capture failed")
            self._status.showMessage("Save failed due to an internal error")
        finally:
            self._capture_in_progress = False
            if getattr(self, '_was_visible', False):
                self.show()

    def _save_clipboard_only(self, pixmap: QPixmap):
        """Copy pixmap to clipboard without saving a file."""
        import tempfile
        try:
            if pixmap.isNull():
                if getattr(self, '_was_visible', False):
                    self.show()
                return
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            pixmap.save(tmp_path, "PNG")
            copy_image_to_clipboard(tmp_path)
            self._notify("Screenshot copied to clipboard", "Not saved to disk")
            self._status.showMessage("Copied to clipboard (not saved)")
        except Exception:
            logger.exception("Clipboard-only capture failed")
            self._status.showMessage("Clipboard copy failed. Check bazzcap.log")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            self._capture_in_progress = False
            if getattr(self, '_was_visible', False):
                self.show()

    def _do_ocr(self, pixmap: QPixmap):
        """Run tesseract OCR on pixmap and copy extracted text to clipboard."""
        import tempfile
        tmp_path = None
        try:
            if pixmap.isNull():
                if getattr(self, '_was_visible', False):
                    self.show()
                return

            import shutil as _shutil
            if not _shutil.which("tesseract"):
                self._notify(
                    "OCR: tesseract not found",
                    "Install tesseract: sudo dnf install tesseract"
                )
                self._status.showMessage(
                    "OCR failed: tesseract not installed"
                )
                self._capture_in_progress = False
                if getattr(self, '_was_visible', False):
                    self.show()
                return

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            pixmap.save(tmp_path, "PNG")

            import subprocess as _sp
            result = _sp.run(
                ["tesseract", tmp_path, "stdout", "--psm", "3"],
                capture_output=True, text=True, timeout=30,
            )
            text = result.stdout.strip()

            if not text:
                self._notify("OCR: no text found", "Could not extract any text from region")
                self._status.showMessage("OCR: no text found in selection")
            else:
                from bazzcap.clipboard import copy_text_to_clipboard
                copy_text_to_clipboard(text)
                preview = text[:60].replace("\n", " ")
                if len(text) > 60:
                    preview += "…"
                self._notify("OCR: text copied to clipboard", preview)
                self._status.showMessage(f"OCR: copied {len(text)} chars to clipboard")
                logger.info("OCR extracted %d chars", len(text))

        except Exception:
            logger.exception("OCR failed")
            self._status.showMessage("OCR failed. Check bazzcap.log")
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
            self._capture_in_progress = False
            if getattr(self, '_was_visible', False):
                self.show()

    def _on_overlay_captured(self, pixmap: QPixmap):
        try:
            for ov in getattr(self, '_overlays', []):
                ov.hide()
                ov.close()
                ov.deleteLater()
            self._overlays = []
            self._overlay = None

            if getattr(self, '_ocr_mode', False):
                self._ocr_mode = False
                self._do_ocr(pixmap)
            elif getattr(self, '_clipboard_only', False):
                self._clipboard_only = False
                self._save_clipboard_only(pixmap)
            else:
                self._save_and_notify(pixmap, "region")
        except Exception:
            logger.exception("Overlay completion crashed")
            self._status.showMessage("Capture finalize crashed. Check bazzcap.log")
            if getattr(self, '_was_visible', False):
                self.show()

    def _on_overlay_cancelled(self):
        for ov in getattr(self, '_overlays', []):
            ov.hide()
            ov.close()
            ov.deleteLater()
        self._overlays = []
        self._overlay = None
        self._capture_in_progress = False
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
            logger.exception("Editor failed to open for %s", path)
            self._status.showMessage(f"Editor error: {e}")
            self.show()

    def _open_path(self, path: str) -> bool:
        target = os.path.abspath(os.path.expanduser(path))
        if QDesktopServices.openUrl(QUrl.fromLocalFile(target)):
            return True

        commands = []
        if IS_MACOS:
            commands.append(["open", target])
        else:
            if is_flatpak():
                commands.append(["flatpak-spawn", "--host", "xdg-open", target])
            commands.append(["xdg-open", target])

        for cmd in commands:
            try:
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=external_command_env(),
                )
                return True
            except OSError:
                continue

        logger.error("Failed to open path: %s", target)
        return False

    def _on_editor_saved(self, path: str):
        if os.path.isfile(path):
            existing = any(entry.filepath == path for entry in self._history.entries)
            if not existing:
                self._history.add(HistoryEntry.create(path, "screenshot", "edited"))
                self._refresh_history()
        if self._config.get("auto_copy_to_clipboard", True):
            copy_image_to_clipboard(path)
        self.show()

    def _selected_history_item(self):
        return self._history_list.currentItem()

    def _selected_history_raw_path(self) -> str | None:
        item = self._selected_history_item()
        if item is None:
            return None
        path = item.data(Qt.ItemDataRole.UserRole)
        return path or None

    def _selected_history_path(self) -> str | None:
        path = self._selected_history_raw_path()
        if not path or not os.path.isfile(path):
            return None
        return path

    def _is_editable_image(self, path: str | None) -> bool:
        if not path or not os.path.isfile(path):
            return False
        return os.path.splitext(path)[1].lower() in (".png", ".jpg", ".jpeg", ".bmp", ".webp")

    def _sync_history_actions(self):
        raw_path = self._selected_history_raw_path()
        path = self._selected_history_path()
        is_image = self._is_editable_image(path)
        has_selection = raw_path is not None
        if hasattr(self, "_btn_edit_history"):
            self._btn_edit_history.setEnabled(is_image)
        if hasattr(self, "_btn_open_history"):
            self._btn_open_history.setEnabled(path is not None)
        if hasattr(self, "_btn_duplicate_history"):
            self._btn_duplicate_history.setEnabled(path is not None)
        if hasattr(self, "_btn_delete_history"):
            self._btn_delete_history.setEnabled(has_selection)

    @staticmethod
    def _build_variant_copy_path(filepath: str, suffix: str) -> str:
        directory = os.path.dirname(filepath)
        stem, ext = os.path.splitext(os.path.basename(filepath))
        candidate = os.path.join(directory, f"{stem}_{suffix}{ext}")
        index = 2
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{stem}_{suffix}_{index}{ext}")
            index += 1
        return candidate

    def _open_selected_history_file(self):
        path = self._selected_history_path()
        if not path:
            self._status.showMessage("Select an existing capture to open.")
            return
        if self._open_path(path):
            self._status.showMessage(f"Opened: {os.path.basename(path)}")
        else:
            self._status.showMessage("Could not open file. Check bazzcap.log")

    def _reveal_selected_history_item(self):
        raw_path = self._selected_history_raw_path()
        if not raw_path:
            self._status.showMessage("Select a capture first.")
            return
        target_dir = os.path.dirname(raw_path) if os.path.dirname(raw_path) else self._config.save_directory
        if self._open_path(target_dir):
            self._status.showMessage(f"Opened folder: {target_dir}")
        else:
            self._status.showMessage("Could not open folder. Check bazzcap.log")

    def _edit_selected_history_item(self):
        path = self._selected_history_path()
        if not self._is_editable_image(path):
            self._status.showMessage("Select a screenshot to edit.")
            return

        edit_path = self._build_variant_copy_path(path, "edited")
        try:
            shutil.copy2(path, edit_path)
        except OSError as e:
            self._status.showMessage(f"Could not create edit copy: {e}")
            return

        self._status.showMessage(f"Editing copy: {os.path.basename(edit_path)}")
        self._open_editor(edit_path)

    def _duplicate_selected_history_item(self):
        path = self._selected_history_path()
        if not path:
            self._status.showMessage("Select an existing capture to duplicate.")
            return

        duplicate_path = self._build_variant_copy_path(path, "copy")
        try:
            shutil.copy2(path, duplicate_path)
        except OSError as e:
            self._status.showMessage(f"Could not duplicate capture: {e}")
            return

        self._history.add(HistoryEntry.create(duplicate_path, "screenshot", "copy"))
        self._refresh_history()
        self._status.showMessage(f"Duplicated: {os.path.basename(duplicate_path)}")

    def _delete_selected_history_item(self):
        raw_path = self._selected_history_raw_path()
        if not raw_path:
            self._status.showMessage("Select a capture to delete.")
            return

        exists = os.path.isfile(raw_path)
        name = os.path.basename(raw_path)
        if exists:
            message = f"Delete '{name}' from disk and remove it from history?"
        else:
            message = f"'{name}' is already missing. Remove it from history?"

        answer = QMessageBox.question(
            self,
            "Delete Capture",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        if exists:
            try:
                os.unlink(raw_path)
            except OSError as e:
                self._status.showMessage(f"Could not delete file: {e}")
                return

        self._history.remove(raw_path)
        self._refresh_history()
        self._status.showMessage(f"Removed: {name}")

    def _remove_missing_history_items(self):
        missing = [entry.filepath for entry in self._history.entries if not os.path.isfile(entry.filepath)]
        if not missing:
            self._status.showMessage("No missing history entries found.")
            return
        for filepath in missing:
            self._history.remove(filepath)
        self._refresh_history()
        self._status.showMessage(f"Removed {len(missing)} missing entr{'y' if len(missing) == 1 else 'ies'} from history.")

    def _show_history_context_menu(self, pos):
        item = self._history_list.itemAt(pos)
        if item is None:
            return
        self._history_list.setCurrentItem(item)
        path = self._selected_history_path()
        menu = QMenu(self._history_list)

        edit_action = menu.addAction("Edit Copy")
        edit_action.setEnabled(self._is_editable_image(path))
        edit_action.triggered.connect(self._edit_selected_history_item)

        reveal_action = menu.addAction("Show in Folder")
        reveal_action.setEnabled(self._selected_history_raw_path() is not None)
        reveal_action.triggered.connect(self._reveal_selected_history_item)

        menu.addSeparator()

        delete_action = menu.addAction("Delete")
        delete_action.setEnabled(self._selected_history_raw_path() is not None)
        delete_action.triggered.connect(self._delete_selected_history_item)

        menu.exec(self._history_list.mapToGlobal(pos))

    def _refresh_history(self):
        self._history.sync_with_directory(self._config.save_directory)
        self._history_list.clear()
        for entry in self._history.entries[:50]:
            icon = {"screenshot": "IMG"}.get(entry.capture_type, "FILE")
            name = os.path.basename(entry.filepath)
            exists = os.path.isfile(entry.filepath)
            size_kb = entry.file_size / 1024 if entry.file_size else 0
            ts = entry.timestamp[:19].replace("T", "  ")
            tags = []
            if entry.mode:
                tags.append(entry.mode)
            if not exists:
                tags.append("missing")
            tag_text = f"  [{' | '.join(tags)}]" if tags else ""
            size_text = f"{size_kb:.0f} KB" if exists else "missing"
            text = f"  [{icon}]  {name}{tag_text}    ({size_text})    {ts}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry.filepath)
            self._history_list.addItem(item)
        self._sync_history_actions()

    def _open_history_item(self, item: QListWidgetItem):
        self._history_list.setCurrentItem(item)
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path or not os.path.isfile(path):
            self._status.showMessage("File not found!")
            return

        ext = os.path.splitext(path)[1].lower()
        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
            self._edit_selected_history_item()
        else:
            if not self._open_path(path):
                self._status.showMessage("Could not open file. Check bazzcap.log")

    def _open_save_dir(self):
        if self._open_path(self._config.save_directory):
            self._status.showMessage("Opened save folder")
        else:
            self._status.showMessage("Could not open save folder. Check bazzcap.log")

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
            if IS_MACOS:
                subprocess.Popen(
                    ["osascript", "-e",
                     f'display notification "{message}" with title "{title}"'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["notify-send", "-a", "BazzCap", "-i", "camera-photo",
                     title, message],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
        except (OSError, FileNotFoundError):
            pass

    def closeEvent(self, event):
        if self._tray_available and self._config.get("minimize_to_tray", True):
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

    def __init__(self, app_icon: QIcon | None = None, parent=None):
        super().__init__(parent)
        self._set_tray_icon(app_icon)
        self.setToolTip("BazzCap")
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _set_tray_icon(self, app_icon: QIcon | None):
        if app_icon is not None and not app_icon.isNull():
            self.setIcon(app_icon)
            return
        self.setIcon(_fallback_app_icon())

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
        menu.addAction("Fullscreen → Clipboard Only",
                       lambda: self.capture_requested.emit("fullscreen_clipboard"))
        menu.addAction("Region → Clipboard Only",
                       lambda: self.capture_requested.emit("region_clipboard"))
        menu.addAction("OCR — Copy Text from Region",
                       lambda: self.capture_requested.emit("ocr"))
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


class _SingleInstanceGuard:

    def __init__(self):
        if IS_MACOS:
            base_dir = os.path.expanduser("~/Library/Application Support/bazzcap")
        else:
            base_dir = os.path.expanduser("~/.config/bazzcap")
        os.makedirs(base_dir, exist_ok=True)
        self._lock_path = os.path.join(base_dir, "bazzcap.lock")
        self._handle = None

    def acquire(self) -> bool:
        self._handle = open(self._lock_path, "w")
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._handle.write(str(os.getpid()))
            self._handle.flush()
            return True
        except OSError:
            try:
                self._handle.close()
            except OSError:
                pass
            self._handle = None
            return False

    def release(self):
        if not self._handle:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            self._handle.close()
        except OSError:
            pass
        self._handle = None


class BazzCapApp:

    def __init__(self):
        self._log_file = setup_logging()
        install_global_exception_handlers()

        self.app = QApplication(sys.argv)
        self.app.setApplicationName("BazzCap")
        self.app.setQuitOnLastWindowClosed(False)
        self._app_icon = load_app_icon()
        self.app.setWindowIcon(self._app_icon)
        self._tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self._tray_probe_timer = QTimer()
        self._tray_probe_timer.setInterval(2500)
        self._tray_probe_timer.timeout.connect(self._ensure_tray_ready)

        self._instance_guard = _SingleInstanceGuard()
        self._single_instance_ok = self._instance_guard.acquire()
        if not self._single_instance_ok:
            QMessageBox.information(
                None,
                "BazzCap Already Running",
                "Only one BazzCap instance can run at a time."
            )
            self._exit_code = 0
            return

        self.config = Config()
        self.history = HistoryManager()
        self.hotkey_manager = HotkeyManager()

        self._hotkey_bridge = _HotkeyBridge()
        self._hotkey_bridge.trigger.connect(
            lambda name, pos: self._on_hotkey_triggered(name, pos)
        )

        self.main_window = MainWindow(self.config, self.history, app_icon=self._app_icon)
        self.main_window._tray_available = self._tray_available

        self.tray = None
        if not self._init_tray():
            logger.warning("System tray unavailable; starting with visible window")
            self._tray_probe_timer.start()
        self._setup_hotkeys()

        self.app._bazzcap_app = self

    def _reregister_hotkeys(self):
        hotkeys = self.config.get("hotkeys", {})
        new_bindings = {}
        for name in [
            "capture_fullscreen", "capture_region", "capture_window",
            "capture_fullscreen_clipboard", "capture_region_clipboard",
            "capture_ocr",
        ]:
            combo = hotkeys.get(name, "")
            if combo:
                new_bindings[name] = combo
        self.hotkey_manager.reregister(new_bindings)

    def _setup_hotkeys(self):
        hotkeys = self.config.get("hotkeys", {})

        all_names = [
            "capture_fullscreen", "capture_region", "capture_window",
            "capture_fullscreen_clipboard", "capture_region_clipboard",
            "capture_ocr",
        ]

        for name in all_names:
            combo = hotkeys.get(name, "")
            if combo:
                def make_callback(n):
                    return lambda cursor_pos=None: self._hotkey_bridge.trigger.emit(n, cursor_pos)
                self.hotkey_manager.register(name, combo, make_callback(name))

        try:
            self.hotkey_manager.start()
        except Exception as e:
            logger.exception("Hotkey manager failed to start")
            print(f"[BazzCap] Hotkey manager failed to start: {e}",
                  flush=True)

    def _on_hotkey_triggered(self, name: str, cursor_pos=None):
        logger.info("Hotkey triggered: name=%s cursor_pos=%s", name, cursor_pos)
        action_map = {
            "capture_fullscreen": lambda: self.main_window._start_capture("fullscreen", cursor_pos),
            "capture_region": lambda: self.main_window._start_capture("region", cursor_pos),
            "capture_window": lambda: self.main_window._start_capture("window", cursor_pos),
            "capture_fullscreen_clipboard": lambda: self.main_window._start_capture(
                "fullscreen", cursor_pos, clipboard_only=True),
            "capture_region_clipboard": lambda: self.main_window._start_capture(
                "region", cursor_pos, clipboard_only=True),
            "capture_ocr": lambda: self.main_window._start_capture("ocr", cursor_pos),
        }
        action = action_map.get(name)
        if action:
            action()

    def _tray_capture(self, mode: str):
        if mode == "fullscreen_clipboard":
            self.main_window._start_capture("fullscreen", clipboard_only=True)
        elif mode == "region_clipboard":
            self.main_window._start_capture("region", clipboard_only=True)
        else:
            self.main_window._start_capture(mode)

    def _init_tray(self) -> bool:
        if self.tray is not None:
            if not self.tray.isVisible():
                self.tray.show()
            return self.tray.isVisible()

        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.main_window._tray_available = False
            return False

        tray = SystemTray(app_icon=self._app_icon)
        tray.capture_requested.connect(self._tray_capture)
        tray.show_requested.connect(self._show_window)
        tray.settings_requested.connect(self.main_window._show_settings)
        tray.hotkey_settings_requested.connect(self.main_window._show_hotkey_settings)
        tray.quit_requested.connect(self._quit)
        tray.show()

        self.tray = tray
        self.main_window._tray_available = tray.isVisible()
        return tray.isVisible()

    def _ensure_tray_ready(self):
        if self._init_tray():
            self._tray_available = True
            self.main_window._tray_available = True
            self._tray_probe_timer.stop()
        else:
            self._tray_available = False
            self.main_window._tray_available = False

    def _show_window(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _quit(self):
        self.hotkey_manager.stop()
        if self._tray_probe_timer.isActive():
            self._tray_probe_timer.stop()
        if self.tray is not None:
            self.tray.hide()
        self._instance_guard.release()
        self.app.quit()

    def run(self) -> int:
        if not getattr(self, "_single_instance_ok", True):
            return getattr(self, "_exit_code", 0)
        self._ensure_tray_ready()
        started_from_autostart = os.environ.get(AUTOSTART_ENV_FLAG) == "1"
        tray_ready = self.tray is not None and self.tray.isVisible()
        should_start_visible = (
            not started_from_autostart
            and (not self.config.get("start_minimized", True) or not tray_ready)
        )
        if should_start_visible:
            self.main_window.show()
        try:
            return self.app.exec()
        except Exception:
            logger.exception("Unhandled crash in Qt event loop")
            raise
        finally:
            self._instance_guard.release()
