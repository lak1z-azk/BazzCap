"""BazzCap main application — capture & recording experience for Linux.

Complete rewrite using custom overlay for region/window/fullscreen capture
instead of delegating to system screenshot tools.
"""

import sys
import os
import time
import subprocess
import tempfile
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
from bazzcap.recorder import ScreenRecorder, RecordingState
from bazzcap.clipboard import copy_image_to_clipboard
from bazzcap.history import HistoryManager, HistoryEntry
from bazzcap.hotkeys import HotkeyManager
from bazzcap.hotkey_settings import HotkeySettingsDialog


# ─── Settings Dialog ────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    """Application settings dialog."""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("BazzCap — Settings")
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # General
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

        general.setLayout(form)
        layout.addWidget(general)

        # Recording
        recording = QGroupBox("Recording")
        rec_form = QFormLayout()

        self._rec_fps = QSpinBox()
        self._rec_fps.setRange(10, 120)
        self._rec_fps.setValue(self._config.get("recording_fps", 30))
        rec_form.addRow("Recording FPS:", self._rec_fps)

        self._gif_fps = QSpinBox()
        self._gif_fps.setRange(5, 30)
        self._gif_fps.setValue(self._config.get("gif_fps", 15))
        rec_form.addRow("GIF FPS:", self._gif_fps)

        self._gif_width = QSpinBox()
        self._gif_width.setRange(320, 3840)
        self._gif_width.setValue(self._config.get("gif_max_width", 640))
        rec_form.addRow("GIF max width:", self._gif_width)

        recording.setLayout(rec_form)
        layout.addWidget(recording)

        # Editor
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

        # Buttons
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
        self._config.set("recording_fps", self._rec_fps.value())
        self._config.set("gif_fps", self._gif_fps.value())
        self._config.set("gif_max_width", self._gif_width.value())
        self._config.set("editor.default_line_width", self._line_width.value())
        self._config.set("editor.default_font_size", self._font_size.value())
        self._config.set("editor.blur_radius", self._blur_radius.value())
        self._config.save()
        self.accept()


# ─── Main Dashboard Window ──────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """BazzCap main window."""

    capture_requested = pyqtSignal(str)  # mode string

    def __init__(self, config: Config, history: HistoryManager,
                 recorder: ScreenRecorder, parent=None):
        super().__init__(parent)
        self._config = config
        self._history = history
        self._recorder = recorder
        self._editor_windows = []
        self._overlay = None

        self.setWindowTitle("BazzCap")
        self.setMinimumSize(750, 550)
        self._apply_dark_theme()
        self._build_ui()
        self._refresh_history()

        # Recording timer
        self._rec_timer = QTimer(self)
        self._rec_timer.timeout.connect(self._update_rec_timer)

    def _apply_dark_theme(self):
        """Apply BazzCap's dark theme."""
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

        # ── Header ──
        header_layout = QHBoxLayout()

        title_layout = QVBoxLayout()
        header = QLabel("BazzCap")
        header.setFont(QFont("Sans", 24, QFont.Weight.Bold))
        header.setStyleSheet("color: #89b4fa;")
        title_layout.addWidget(header)

        subtitle = QLabel("Screenshot & Recording for Linux")
        subtitle.setStyleSheet("color: #6c7086; font-size: 12px;")
        title_layout.addWidget(subtitle)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # Quick settings buttons
        btn_settings = QPushButton("Settings")
        btn_settings.setFixedHeight(36)
        btn_settings.clicked.connect(lambda: self._show_settings())
        header_layout.addWidget(btn_settings)

        btn_hotkeys = QPushButton("Hotkeys")
        btn_hotkeys.setFixedHeight(36)
        btn_hotkeys.clicked.connect(lambda: self._show_hotkey_settings())
        header_layout.addWidget(btn_hotkeys)

        layout.addLayout(header_layout)

        # ── Capture Buttons ──
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

        # ── Recording Buttons ──
        rec_group = QGroupBox("Recording")
        rec_layout = QHBoxLayout()
        rec_layout.setSpacing(8)

        self._btn_record = QPushButton("Start Video Recording")
        self._btn_record.setMinimumHeight(50)
        self._btn_record.setToolTip(self._hotkey_tip("start_recording"))
        self._btn_record.clicked.connect(self._toggle_recording)
        rec_layout.addWidget(self._btn_record)

        self._btn_gif = QPushButton("Record GIF")
        self._btn_gif.setMinimumHeight(50)
        self._btn_gif.setToolTip(self._hotkey_tip("start_gif"))
        self._btn_gif.clicked.connect(self._toggle_gif_recording)
        rec_layout.addWidget(self._btn_gif)

        self._rec_label = QLabel("")
        self._rec_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rec_label.setStyleSheet(
            "color: #f38ba8; font-weight: bold; font-size: 16px; min-width: 100px;"
        )
        rec_layout.addWidget(self._rec_label)

        rec_group.setLayout(rec_layout)
        layout.addWidget(rec_group)

        # ── History ──
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

        # ── Status Bar ──
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        from bazzcap.capture import detect_available_backends
        backends = detect_available_backends()
        self._status.showMessage(
            f"Ready  |  Backends: {', '.join(backends) if backends else 'XDG Portal'}"
        )

    def _hotkey_tip(self, name: str) -> str:
        """Get tooltip showing the configured hotkey."""
        hotkeys = self._config.get("hotkeys", {})
        hk = hotkeys.get(name, "")
        if hk:
            display = hk.replace("<Ctrl>", "Ctrl+").replace(
                "<Shift>", "Shift+").replace("<Alt>", "Alt+").replace(
                "<Super>", "Super+")
            return f"Hotkey: {display}"
        return "No hotkey configured"

    # ── Capture Flow ──

    def _start_capture(self, mode: str, cursor_pos=None):
        """Start the capture process:
        1. Hide main window if visible
        2. Grab screen via portal
        3. Show custom overlay
        """
        self._was_visible = self.isVisible()
        self.hide()
        QApplication.processEvents()

        # Small delay to ensure window is hidden
        QTimer.singleShot(250, lambda: self._do_overlay_capture(mode, cursor_pos))

    def _do_overlay_capture(self, mode: str, cursor_pos=None):
        """Grab screen and show overlay."""
        self._status.showMessage("Grabbing screen...")

        # Grab the full screen
        screenshot = grab_screenshot_via_portal()

        if screenshot is None or screenshot.isNull():
            self._status.showMessage("Failed to grab screen!")
            self.show()
            self._notify("Capture failed", "Could not grab screen")
            return

        # Map mode string to overlay mode
        overlay_mode = {
            "fullscreen": RegionCaptureOverlay.MODE_FULLSCREEN,
            "region": RegionCaptureOverlay.MODE_REGION,
            "window": RegionCaptureOverlay.MODE_REGION,  # window = region select
        }.get(mode, RegionCaptureOverlay.MODE_REGION)

        # Create overlay — pass cursor_pos so it knows which screen to use.
        # QCursor.pos() doesn't work on Wayland without a visible window,
        # so the cursor position is captured at hotkey trigger time via xdotool.
        self._overlay = RegionCaptureOverlay(screenshot, overlay_mode,
                                              cursor_pos=cursor_pos)
        self._overlay.capture_completed.connect(self._on_overlay_captured)
        self._overlay.capture_cancelled.connect(self._on_overlay_cancelled)

        # Place overlay on the correct screen on Wayland:
        # 1. Force native window creation via winId()
        # 2. Set the QWindow's screen BEFORE showing
        # 3. Then showFullScreen() goes to the right monitor
        target = self._overlay._target_screen
        if target:
            self._overlay.winId()  # force native window handle
            if self._overlay.windowHandle():
                self._overlay.windowHandle().setScreen(target)
        self._overlay.showFullScreen()

    def _on_overlay_captured(self, pixmap: QPixmap):
        """Handle capture from the overlay — auto-save + auto-clipboard."""
        if self._overlay:
            self._overlay.close()
            self._overlay.deleteLater()
            self._overlay = None

        if pixmap.isNull():
            if getattr(self, '_was_visible', False):
                self.show()
            return

        # Save the capture
        path = self._config.generate_filepath()
        ext = self._config.get("image_format", "png").upper()
        quality = 95 if ext in ("JPG", "JPEG") else -1
        pixmap.save(path, ext, quality)

        if os.path.isfile(path):
            # Add to history
            entry = HistoryEntry.create(path, "screenshot", "region")
            self._history.add(entry)
            self._refresh_history()

            # Auto-clipboard
            copy_image_to_clipboard(path)

            # Notification
            self._notify("Screenshot saved & copied",
                         os.path.basename(path))

            self._status.showMessage(f"Saved: {path}")
        else:
            self._status.showMessage("Failed to save capture!")

        # Only re-show the main window if it was visible before capture
        if getattr(self, '_was_visible', False):
            self.show()

    def _on_overlay_cancelled(self):
        """Handle overlay cancellation."""
        if self._overlay:
            self._overlay.close()
            self._overlay.deleteLater()
            self._overlay = None
        # Only re-show the main window if it was visible before capture
        if getattr(self, '_was_visible', False):
            self.show()
        self._status.showMessage("Capture cancelled")

    # ── Editor ──

    def _open_editor(self, path: str):
        """Open the annotation editor (for history items)."""
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

    # ── Recording ──

    def _toggle_recording(self):
        if self._recorder.is_recording:
            path = self._recorder.stop_recording()
            self._rec_timer.stop()
            self._rec_label.setText("")
            self._btn_record.setText("Start Video Recording")
            self._btn_gif.setEnabled(True)

            if path:
                entry = HistoryEntry.create(path, "recording")
                self._history.add(entry)
                self._refresh_history()
                self._notify("Recording saved", os.path.basename(path))
        else:
            path = self._config.generate_filepath("mp4")
            self.hide()
            QApplication.processEvents()
            QTimer.singleShot(300, lambda: self._start_recording(path))

    def _start_recording(self, path):
        success = self._recorder.start_recording(path)
        if success:
            self._btn_record.setText("Stop Recording")
            self._btn_gif.setEnabled(False)
            self._rec_timer.start(1000)
            self.show()
        else:
            self.show()
            self._status.showMessage("Recording failed! Is FFmpeg installed?")

    def _toggle_gif_recording(self):
        if self._recorder.is_recording:
            video_path = self._recorder.stop_recording()
            self._rec_timer.stop()
            self._rec_label.setText("")
            self._btn_gif.setText("Record GIF")
            self._btn_record.setEnabled(True)

            if video_path:
                self._status.showMessage("Converting to GIF...")
                self._recorder.convert_to_gif(video_path, callback=self._on_gif_done)
        else:
            path = self._config.generate_filepath("mp4")
            self.hide()
            QApplication.processEvents()
            QTimer.singleShot(300, lambda: self._start_gif_recording(path))

    def _start_gif_recording(self, path):
        success = self._recorder.start_recording(path)
        if success:
            self._btn_gif.setText("Stop & Convert to GIF")
            self._btn_record.setEnabled(False)
            self._rec_timer.start(1000)
            self.show()
        else:
            self.show()
            self._status.showMessage("Recording failed!")

    def _on_gif_done(self, gif_path, error):
        QTimer.singleShot(0, lambda: self._handle_gif_done(gif_path, error))

    def _handle_gif_done(self, gif_path, error):
        if gif_path:
            entry = HistoryEntry.create(gif_path, "gif")
            self._history.add(entry)
            self._refresh_history()
            self._notify("GIF saved", os.path.basename(gif_path))
            self._status.showMessage(f"GIF saved: {gif_path}")
        else:
            self._status.showMessage(f"GIF conversion failed: {error}")

    def _update_rec_timer(self):
        elapsed = int(self._recorder.elapsed)
        mins, secs = elapsed // 60, elapsed % 60
        self._rec_label.setText(f"REC  {mins:02d}:{secs:02d}")

    # ── History ──

    def _refresh_history(self):
        self._history_list.clear()
        for entry in self._history.entries[:50]:
            icon = {"screenshot": "IMG", "recording": "VID", "gif": "GIF"}.get(
                entry.capture_type, "FILE"
            )
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

    # ── Settings ──

    def _show_settings(self):
        dialog = SettingsDialog(self._config, self)
        dialog.exec()

    def _show_hotkey_settings(self):
        dialog = HotkeySettingsDialog(self._config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Re-register GNOME shortcuts with updated bindings
            app_obj = QApplication.instance()
            if hasattr(app_obj, '_bazzcap_app') and hasattr(app_obj._bazzcap_app, '_reregister_hotkeys'):
                app_obj._bazzcap_app._reregister_hotkeys()
            self._status.showMessage("Hotkeys updated and applied!")

    # ── Notifications ──

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


# ─── System Tray ─────────────────────────────────────────────────────────────

class SystemTray(QSystemTrayIcon):
    """System tray with quick-access menu."""

    capture_requested = pyqtSignal(str)  # mode
    recording_requested = pyqtSignal()
    gif_requested = pyqtSignal()
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
        # Blue circle
        painter.setBrush(QBrush(QColor(137, 180, 250)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(1, 1, 30, 30)
        # "B" letter
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
        menu.addAction("Record Video", lambda: self.recording_requested.emit())
        menu.addAction("Record GIF", lambda: self.gif_requested.emit())
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
            # Single click — do nothing (RMB context menu handles actions)
            pass
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            self.capture_requested.emit("region")

    def update_recording_state(self, recording: bool):
        if recording:
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(QColor(243, 139, 168)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(1, 1, 30, 30)
            painter.end()
            self.setIcon(QIcon(pixmap))
            self.setToolTip("BazzCap — Recording...")
        else:
            self._create_icon()
            self.setToolTip("BazzCap")


# ─── Application Controller ─────────────────────────────────────────────────

# ─── Thread-safe hotkey bridge ───────────────────────────────────────────────

class _HotkeyBridge(QObject):
    """Bridge to invoke hotkey callbacks on the Qt main thread."""
    trigger = pyqtSignal(str, object)  # name, cursor_pos (tuple or None)


class BazzCapApp:
    """Main application controller."""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("BazzCap")
        self.app.setQuitOnLastWindowClosed(False)

        # Core
        self.config = Config()
        self.history = HistoryManager()
        self.recorder = ScreenRecorder(self.config)
        self.hotkey_manager = HotkeyManager()

        self.recorder.set_callbacks(on_state_change=self._on_rec_state_change)

        # Hotkey bridge for thread-safe signaling
        self._hotkey_bridge = _HotkeyBridge()
        self._hotkey_bridge.trigger.connect(
            lambda name, pos: self._on_hotkey_triggered(name, pos)
        )

        # UI
        self.main_window = MainWindow(self.config, self.history, self.recorder)
        self.tray = SystemTray()

        # Connect tray signals
        self.tray.capture_requested.connect(self._tray_capture)
        self.tray.recording_requested.connect(self.main_window._toggle_recording)
        self.tray.gif_requested.connect(self.main_window._toggle_gif_recording)
        self.tray.show_requested.connect(self._show_window)
        self.tray.settings_requested.connect(self.main_window._show_settings)
        self.tray.hotkey_settings_requested.connect(self.main_window._show_hotkey_settings)
        self.tray.quit_requested.connect(self._quit)

        self.tray.show()
        self._setup_hotkeys()

        # Store ref so MainWindow can trigger re-registration
        self.app._bazzcap_app = self

    def _reregister_hotkeys(self):
        """Re-register global hotkeys after settings change."""
        hotkeys = self.config.get("hotkeys", {})
        new_bindings = {}
        for name in ["capture_fullscreen", "capture_region", "capture_window",
                     "start_recording", "start_gif"]:
            combo = hotkeys.get(name, "")
            if combo:
                new_bindings[name] = combo
        self.hotkey_manager.reregister(new_bindings)

    def _setup_hotkeys(self):
        hotkeys = self.config.get("hotkeys", {})

        # All callbacks go through the bridge to ensure main-thread execution
        all_names = [
            "capture_fullscreen", "capture_region", "capture_window",
            "start_recording", "start_gif",
        ]

        for name in all_names:
            combo = hotkeys.get(name, "")
            if combo:
                # Use a factory to capture 'name' correctly in the closure
                def make_callback(n):
                    return lambda cursor_pos=None: self._hotkey_bridge.trigger.emit(n, cursor_pos)
                self.hotkey_manager.register(name, combo, make_callback(name))

        try:
            self.hotkey_manager.start()
        except Exception:
            pass

    def _on_hotkey_triggered(self, name: str, cursor_pos=None):
        """Handle hotkey trigger on the main thread."""
        action_map = {
            "capture_fullscreen": lambda: self.main_window._start_capture("fullscreen", cursor_pos),
            "capture_region": lambda: self.main_window._start_capture("region", cursor_pos),
            "capture_window": lambda: self.main_window._start_capture("window", cursor_pos),
            "start_recording": lambda: self.main_window._toggle_recording(),
            "start_gif": lambda: self.main_window._toggle_gif_recording(),
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

    def _on_rec_state_change(self, state: RecordingState):
        self.tray.update_recording_state(state == RecordingState.RECORDING)

    def _quit(self):
        if self.recorder.is_recording:
            self.recorder.stop_recording()
        self.hotkey_manager.stop()
        self.tray.hide()
        self.app.quit()

    def run(self) -> int:
        if not self.config.get("start_minimized", False):
            self.main_window.show()
        return self.app.exec()
