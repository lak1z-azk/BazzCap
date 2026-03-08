"""Custom screen capture overlay for BazzCap — region selector with annotations.

Workflow:
  1. Grab a fullscreen screenshot via XDG portal
  2. Show frozen overlay covering entire screen
  3. Small annotation toolbar appears at the TOP of the screen
  4. User optionally picks an annotation tool (arrow, rect, line, text, blur…)
  5. User drags to select a region
  6. If an annotation tool was active: user can draw on the selected region
  7. Press Enter / click checkmark to finish  →  auto-save + clipboard
  8. If NO tool was active: capture finishes immediately on mouse-release
"""

import subprocess
import os
import math
import shutil
import tempfile

from PyQt6.QtWidgets import (
    QWidget, QApplication, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QColorDialog, QInputDialog,
    QDialog, QDialogButtonBox, QFormLayout, QTextEdit,
    QSpinBox, QCheckBox, QComboBox, QGroupBox,
    QFontComboBox, QSlider,
)
from PyQt6.QtCore import (
    Qt, QRect, QPoint, QSize, QTimer, pyqtSignal, QRectF, QPointF, QLineF,
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QBrush, QFont, QCursor,
    QScreen, QGuiApplication, QImage, QRegion, QPainterPath,
    QKeyEvent, QMouseEvent, QFontMetrics,
)


# ─── Annotation Tool Constants ──────────────────────────────────────────────

class Tool:
    NONE = "none"
    ARROW = "arrow"
    RECT = "rect"
    FILLED_RECT = "filled_rect"
    ELLIPSE = "ellipse"
    LINE = "line"
    FREEHAND = "freehand"
    TEXT = "text"
    BLUR = "blur"
    HIGHLIGHT = "highlight"
    NUMBERED = "numbered"


# ─── Annotation Item ────────────────────────────────────────────────────────

class AnnotationItem:
    """One drawn annotation on the canvas."""
    def __init__(self, tool: str, color: QColor, width: int,
                 start: QPoint, end: QPoint = None, text: str = "",
                 points: list = None, number: int = 0,
                 font_family: str = "Sans", font_size: int = 0,
                 bold: bool = False, italic: bool = False,
                 curved: bool = False,
                 blur_strength: int = 8,
                 text_color: QColor = None):
        self.tool = tool
        self.color = QColor(color)
        self.width = width
        self.start = QPoint(start)
        self.end = QPoint(end) if end else QPoint(start)
        self.text = text
        self.points = [QPoint(p) for p in points] if points else []
        self.number = number
        # Text formatting
        self.font_family = font_family
        self.font_size = font_size   # 0 = auto from pen width
        self.bold = bold
        self.italic = italic
        self.curved = curved
        # Blur intensity (lower = stronger blur, higher = milder)
        self.blur_strength = blur_strength
        # Text color for numbered annotations (None = auto-contrast)
        self.text_color = QColor(text_color) if text_color else None


# ─── Text Format Dialog ─────────────────────────────────────────────────────

class TextFormatDialog(QDialog):
    """Dialog for entering annotation text with formatting options."""

    # Remember last-used settings across instances in the same session
    _last_family = "Sans"
    _last_size = 24
    _last_bold = False
    _last_italic = False
    _last_curved = False

    def __init__(self, parent=None, initial_color: QColor = None):
        super().__init__(parent)
        self.setWindowTitle("Add Text Annotation")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        # ── Text input ──
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("Type your text here…")
        self._text_edit.setMaximumHeight(100)
        layout.addWidget(QLabel("Text:"))
        layout.addWidget(self._text_edit)

        # ── Formatting group ──
        fmt_group = QGroupBox("Formatting")
        fmt_layout = QFormLayout(fmt_group)

        self._font_combo = QFontComboBox()
        self._font_combo.setCurrentFont(QFont(self._last_family))
        fmt_layout.addRow("Font:", self._font_combo)

        self._size_spin = QSpinBox()
        self._size_spin.setRange(8, 200)
        self._size_spin.setValue(self._last_size)
        self._size_spin.setSuffix(" px")
        fmt_layout.addRow("Size:", self._size_spin)

        self._bold_cb = QCheckBox("Bold")
        self._bold_cb.setChecked(self._last_bold)
        self._italic_cb = QCheckBox("Italic")
        self._italic_cb.setChecked(self._last_italic)
        style_row = QHBoxLayout()
        style_row.addWidget(self._bold_cb)
        style_row.addWidget(self._italic_cb)
        fmt_layout.addRow("Style:", style_row)

        self._curved_cb = QCheckBox("Curved (arc text)")
        self._curved_cb.setChecked(self._last_curved)
        fmt_layout.addRow("", self._curved_cb)

        layout.addWidget(fmt_group)

        # ── Preview ──
        self._preview = QLabel()
        self._preview.setMinimumHeight(50)
        self._preview.setStyleSheet(
            "background: #1e1e1e; border: 1px solid #555; border-radius: 4px; padding: 6px;"
        )
        layout.addWidget(QLabel("Preview:"))
        layout.addWidget(self._preview)

        # ── Buttons ──
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Connect preview updates
        self._text_edit.textChanged.connect(self._update_preview)
        self._font_combo.currentFontChanged.connect(self._update_preview)
        self._size_spin.valueChanged.connect(self._update_preview)
        self._bold_cb.toggled.connect(self._update_preview)
        self._italic_cb.toggled.connect(self._update_preview)

        self._color = initial_color or QColor(255, 255, 255)
        self._update_preview()

        # Dark theme
        self.setStyleSheet("""
            QDialog { background: #2b2b2b; color: #ddd; }
            QGroupBox { color: #aaa; border: 1px solid #555; border-radius: 4px;
                        margin-top: 8px; padding-top: 14px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; }
            QLabel { color: #ccc; }
            QTextEdit, QSpinBox, QComboBox, QFontComboBox {
                background: #363636; color: #eee; border: 1px solid #555;
                border-radius: 3px; padding: 3px;
            }
            QCheckBox { color: #ccc; }
            QPushButton { background: #444; color: #eee; border: 1px solid #666;
                          border-radius: 3px; padding: 5px 14px; }
            QPushButton:hover { background: #555; }
        """)

    def _update_preview(self, *_args):
        txt = self._text_edit.toPlainText() or "Sample text"
        font = self.selected_font()
        self._preview.setFont(font)
        color_hex = self._color.name()
        self._preview.setStyleSheet(
            f"background: #1e1e1e; border: 1px solid #555; border-radius: 4px;"
            f" padding: 6px; color: {color_hex};"
        )
        display = txt[:60] + ("…" if len(txt) > 60 else "")
        if self._curved_cb.isChecked():
            display = "⟳ " + display
        self._preview.setText(display)

    def selected_font(self) -> QFont:
        font = QFont(self._font_combo.currentFont().family(),
                     self._size_spin.value())
        font.setBold(self._bold_cb.isChecked())
        font.setItalic(self._italic_cb.isChecked())
        return font

    def result_data(self) -> dict:
        """Return all formatting data."""
        TextFormatDialog._last_family = self._font_combo.currentFont().family()
        TextFormatDialog._last_size = self._size_spin.value()
        TextFormatDialog._last_bold = self._bold_cb.isChecked()
        TextFormatDialog._last_italic = self._italic_cb.isChecked()
        TextFormatDialog._last_curved = self._curved_cb.isChecked()
        return {
            "text": self._text_edit.toPlainText(),
            "font_family": self._font_combo.currentFont().family(),
            "font_size": self._size_spin.value(),
            "bold": self._bold_cb.isChecked(),
            "italic": self._italic_cb.isChecked(),
            "curved": self._curved_cb.isChecked(),
        }


# ─── Top Annotation Toolbar ─────────────────────────────────────────────────

class AnnotationToolbar(QWidget):
    """Small floating toolbar at the top of the screen with annotation tools."""

    tool_selected = pyqtSignal(str)
    color_changed = pyqtSignal(object)
    blur_changed = pyqtSignal(int)
    undo_requested = pyqtSignal()
    confirm_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setFixedHeight(38)
        self._current_tool = Tool.NONE
        self._color = QColor(255, 0, 0)
        self._blur_strength = 8
        self._buttons: dict[str, QPushButton] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(2)

        btn_style = """
            QPushButton {
                background: rgba(30,30,30,220);
                color: #ddd;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 13px;
                min-width: 28px;
            }
            QPushButton:hover { background: rgba(60,100,200,220); border-color: #88f; }
            QPushButton:checked { background: rgba(40,80,180,240); border: 2px solid #aaf; }
        """

        tools = [
            (Tool.ARROW,     "↗", "Arrow (A)"),
            (Tool.RECT,      "▢", "Rectangle (R)"),
            (Tool.ELLIPSE,   "○", "Ellipse (E)"),
            (Tool.LINE,      "╱", "Line (L)"),
            (Tool.FREEHAND,  "✎", "Freehand (D)"),
            (Tool.TEXT,       "T", "Text"),
            (Tool.BLUR,      "▦", "Blur (B)"),
            (Tool.HIGHLIGHT,  "█", "Highlight (H)"),
            (Tool.NUMBERED,  "#", "Numbered (N)"),
        ]

        for tool_id, icon, tooltip in tools:
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setStyleSheet(btn_style)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, t=tool_id: self._on_tool(t))
            layout.addWidget(btn)
            self._buttons[tool_id] = btn

        # Separator
        sep = QLabel("│")
        sep.setStyleSheet("color: #555; font-size: 16px;")
        layout.addWidget(sep)

        # Blur slider (visible only when blur tool selected)
        self._blur_label = QLabel("Blur:")
        self._blur_label.setStyleSheet("color: #aaa; font-size: 11px;")
        self._blur_label.setVisible(False)
        layout.addWidget(self._blur_label)

        self._blur_slider = QSlider(Qt.Orientation.Horizontal)
        self._blur_slider.setRange(2, 32)
        self._blur_slider.setValue(self._blur_strength)
        self._blur_slider.setFixedWidth(90)
        self._blur_slider.setToolTip("Blur intensity (left = strong, right = subtle)")
        self._blur_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: #444; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #0af; width: 12px; margin: -4px 0;
                                         border-radius: 6px; }
        """)
        self._blur_slider.setVisible(False)
        self._blur_slider.valueChanged.connect(self._on_blur_changed)
        layout.addWidget(self._blur_slider)

        sep_blur = QLabel("│")
        sep_blur.setStyleSheet("color: #555; font-size: 16px;")
        self._blur_sep = sep_blur
        self._blur_sep.setVisible(False)
        layout.addWidget(sep_blur)

        # Color button
        self._color_btn = QPushButton("●")
        self._color_btn.setToolTip("Color (C)")
        self._color_btn.setStyleSheet(
            btn_style + f"\nQPushButton {{ color: {self._color.name()}; font-size: 18px; }}"
        )
        self._color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color_btn.clicked.connect(self._pick_color)
        layout.addWidget(self._color_btn)

        # Undo
        btn_undo = QPushButton("↩")
        btn_undo.setToolTip("Undo (Ctrl+Z)")
        btn_undo.setStyleSheet(btn_style)
        btn_undo.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_undo.clicked.connect(self.undo_requested.emit)
        layout.addWidget(btn_undo)

        sep2 = QLabel("│")
        sep2.setStyleSheet("color: #555; font-size: 16px;")
        layout.addWidget(sep2)

        # Confirm
        btn_ok = QPushButton("✓")
        btn_ok.setToolTip("Confirm (Enter)")
        btn_ok.setStyleSheet(
            btn_style.replace("#ddd", "#4f4").replace(
                "rgba(30,30,30,220)", "rgba(20,60,20,220)")
        )
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.clicked.connect(self.confirm_requested.emit)
        layout.addWidget(btn_ok)

        # Cancel
        btn_cancel = QPushButton("✕")
        btn_cancel.setToolTip("Cancel (Esc)")
        btn_cancel.setStyleSheet(
            btn_style.replace("#ddd", "#f44").replace(
                "rgba(30,30,30,220)", "rgba(60,20,20,220)")
        )
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(btn_cancel)

        self.setStyleSheet("background: transparent;")

    def _on_tool(self, tool_id: str):
        if self._current_tool == tool_id:
            # Deselect → back to plain capture
            self._current_tool = Tool.NONE
            self._buttons[tool_id].setChecked(False)
        else:
            self._current_tool = tool_id
            for tid, b in self._buttons.items():
                b.setChecked(tid == tool_id)
        self.tool_selected.emit(self._current_tool)
        self._update_blur_visibility()

    def select_tool(self, tool_id: str):
        """Programmatically select a tool (keyboard shortcut)."""
        if tool_id == self._current_tool:
            self._current_tool = Tool.NONE
            for b in self._buttons.values():
                b.setChecked(False)
        else:
            self._current_tool = tool_id
            for tid, b in self._buttons.items():
                b.setChecked(tid == tool_id)
        self.tool_selected.emit(self._current_tool)
        self._update_blur_visibility()

    def _update_blur_visibility(self):
        show = self._current_tool == Tool.BLUR
        self._blur_label.setVisible(show)
        self._blur_slider.setVisible(show)
        self._blur_sep.setVisible(show)

    def _on_blur_changed(self, value: int):
        self._blur_strength = value
        self.blur_changed.emit(value)

    def _pick_color(self):
        color = QColorDialog.getColor(
            self._color, self, "Annotation Color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if color.isValid():
            self._color = color
            self._color_btn.setStyleSheet(
                f"""QPushButton {{
                    background: rgba(30,30,30,220);
                    color: {color.name()};
                    border: 1px solid #555;
                    border-radius: 3px;
                    padding: 4px 8px;
                    font-size: 18px;
                    min-width: 28px;
                }}
                QPushButton:hover {{ background: rgba(60,100,200,220); }}"""
            )
            self.color_changed.emit(color)

    @property
    def current_tool(self):
        return self._current_tool

    @property
    def current_color(self):
        return QColor(self._color)


# ─── Magnifier Widget ───────────────────────────────────────────────────────

class MagnifierWidget(QWidget):
    """Small magnifier lens that follows the cursor."""

    def __init__(self, source_pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._source = source_pixmap
        self._zoom = 4
        self._size = 100
        self._cursor_pos = QPoint(0, 0)
        self.setFixedSize(self._size + 2, self._size + 24)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def update_position(self, pos: QPoint):
        self._cursor_pos = pos
        offset = 20
        x = pos.x() + offset
        y = pos.y() + offset
        # Use the parent widget's size for bounds (works on single-screen overlay)
        parent = self.parentWidget()
        if parent:
            pw, ph = parent.width(), parent.height()
            if x + self.width() > pw:
                x = pos.x() - offset - self.width()
            if y + self.height() > ph:
                y = pos.y() - offset - self.height()
        self.move(x, y)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        region_size = self._size // self._zoom
        sx = self._cursor_pos.x() - region_size // 2
        sy = self._cursor_pos.y() - region_size // 2
        cropped = self._source.copy(QRect(sx, sy, region_size, region_size))
        zoomed = cropped.scaled(
            self._size, self._size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        p.setBrush(QBrush(QColor(30, 30, 30, 230)))
        p.setPen(QPen(QColor(100, 150, 255), 2))
        p.drawRoundedRect(0, 0, self.width() - 1, self.height() - 1, 4, 4)
        p.drawPixmap(1, 1, zoomed)
        # Crosshair
        c = self._size // 2
        p.setPen(QPen(QColor(255, 50, 50, 180), 1))
        p.drawLine(c, 1, c, self._size)
        p.drawLine(1, c, self._size, c)
        # Pixel grid
        p.setPen(QPen(QColor(100, 100, 100, 50), 1))
        for i in range(0, self._size, self._zoom):
            p.drawLine(i, 1, i, self._size)
            p.drawLine(1, i, self._size, i)
        # Color hex
        img = self._source.toImage()
        px = self._cursor_pos
        if 0 <= px.x() < img.width() and 0 <= px.y() < img.height():
            clr = QColor(img.pixel(px.x(), px.y()))
            p.setPen(QColor(200, 200, 200))
            p.setFont(QFont("Monospace", 8))
            p.drawText(
                QRect(0, self._size + 2, self._size, 20),
                Qt.AlignmentFlag.AlignCenter,
                f"#{clr.red():02X}{clr.green():02X}{clr.blue():02X}",
            )
        p.end()


# ─── Region Capture Overlay ─────────────────────────────────────────────────

class RegionCaptureOverlay(QWidget):
    """Full-screen overlay for region capture + inline annotation.

    Phases:
      SELECTING  – user drags to pick a rectangular region
      ANNOTATING – user draws on the selected region (if a tool was active)
    """

    capture_completed = pyqtSignal(QPixmap)
    capture_cancelled = pyqtSignal()
    overlay_activated = pyqtSignal(object)

    MODE_REGION = "region"
    MODE_FULLSCREEN = "fullscreen"

    PHASE_SELECT = "select"
    PHASE_ANNOTATE = "annotate"

    def __init__(self, screenshot: QPixmap, mode: str = "region",
                 parent=None, screen=None):
        super().__init__(parent)
        self._mode = mode
        self._active = True

        target = screen if screen else QGuiApplication.primaryScreen()
        self._target_screen = target

        screen_geo = target.geometry()
        self._screen_geo = screen_geo

        self._screenshot = screenshot.copy(
            screen_geo.x(), screen_geo.y(),
            screen_geo.width(), screen_geo.height(),
        )
        self._dimmed = self._create_dimmed(self._screenshot)

        self._phase = self.PHASE_SELECT

        self._selecting = False
        self._sel_start = QPoint()
        self._sel_end = QPoint()
        self._sel_rect = QRect()
        self._has_selection = False

        self._tool = Tool.NONE
        self._color = QColor(255, 0, 0)
        self._pen_width = 3
        self._blur_strength = 8
        self._annotations: list[AnnotationItem] = []
        self._drawing = False
        self._draw_start = QPoint()
        self._draw_end = QPoint()
        self._freehand_points: list[QPoint] = []
        self._number_counter = 1

        self._dragging_ann = None
        self._dragging_ann_idx = -1
        self._drag_offset = QPoint()

        self._hovered_ann_idx = -1

        self._mouse_pos = QPoint()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._magnifier = MagnifierWidget(self._screenshot, self)
        self._magnifier.hide()

        self._toolbar = AnnotationToolbar(self)
        self._toolbar.tool_selected.connect(self._on_tool_selected)
        self._toolbar.color_changed.connect(self._on_color_changed)
        self._toolbar.blur_changed.connect(self._on_blur_changed)
        self._toolbar.undo_requested.connect(self._undo)
        self._toolbar.confirm_requested.connect(self._confirm)
        self._toolbar.cancel_requested.connect(self._cancel)

        tw = self._toolbar.sizeHint().width()
        self._toolbar.move((screen_geo.width() - tw) // 2, 6)
        self._toolbar.show()
        self._toolbar.raise_()

        self.setMouseTracking(True)

        if mode == self.MODE_FULLSCREEN:
            if len(QGuiApplication.screens()) <= 1:
                QTimer.singleShot(100, self._capture_fullscreen)

    @staticmethod
    def _create_dimmed(pixmap: QPixmap) -> QPixmap:
        dimmed = pixmap.copy()
        p = QPainter(dimmed)
        p.fillRect(dimmed.rect(), QColor(0, 0, 0, 100))
        p.end()
        return dimmed

    # ── Tool / color callbacks ──

    def _on_tool_selected(self, tool: str):
        self._tool = tool

    def _on_color_changed(self, color):
        self._color = QColor(color)

    def _on_blur_changed(self, value: int):
        self._blur_strength = value

    # ── Paint ──

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.drawPixmap(0, 0, self._dimmed)

        if self._has_selection:
            sel = self._sel_rect.normalized()
            if sel.width() > 0 and sel.height() > 0:
                # Bright (original) screenshot inside selection
                p.drawPixmap(sel, self._screenshot, sel)

                # Selection border
                p.setPen(QPen(QColor(0, 140, 255), 2, Qt.PenStyle.SolidLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(sel)

                # Corner handles
                hs = 5
                p.setBrush(QBrush(QColor(0, 140, 255)))
                p.setPen(QPen(QColor(255, 255, 255), 1))
                for c in [sel.topLeft(), sel.topRight(),
                          sel.bottomLeft(), sel.bottomRight()]:
                    p.drawRect(c.x() - hs, c.y() - hs, hs * 2, hs * 2)

                # Dimension label
                dim = f"{sel.width()} × {sel.height()}"
                font = QFont("Monospace", 10, QFont.Weight.Bold)
                p.setFont(font)
                fm = p.fontMetrics()
                tw = fm.horizontalAdvance(dim) + 12
                th = fm.height() + 8
                lx = sel.x()
                ly = sel.bottom() + 5
                if ly + th > self.height():
                    ly = sel.top() - th - 5
                p.setBrush(QBrush(QColor(20, 20, 20, 210)))
                p.setPen(QPen(QColor(0, 140, 255), 1))
                p.drawRoundedRect(lx, ly, tw, th, 3, 3)
                p.setPen(QColor(220, 220, 220))
                p.drawText(QRect(lx + 6, ly + 4, tw - 12, th - 8),
                           Qt.AlignmentFlag.AlignCenter, dim)

        # Annotations on full screen (not clipped to selection)
        self._paint_annotations(p)
        if self._drawing:
            self._paint_current_annotation(p)

        # Highlight the annotation being dragged
        if self._dragging_ann is not None:
            self._paint_drag_highlight(p)
        # Highlight hovered annotation (delete hint)
        elif self._hovered_ann_idx >= 0:
            self._paint_hover_highlight(p)

        # Crosshair (selection phase, not while dragging/drawing/moving)
        if self._phase == self.PHASE_SELECT and not self._selecting and not self._drawing and self._dragging_ann is None:
            pen = QPen(QColor(0, 140, 255, 120), 1, Qt.PenStyle.DashLine)
            p.setPen(pen)
            mx, my = self._mouse_pos.x(), self._mouse_pos.y()
            p.drawLine(mx, 0, mx, self.height())
            p.drawLine(0, my, self.width(), my)

            # Coordinate label near cursor
            coord = f"X: {mx}  Y: {my}"
            font = QFont("Monospace", 9)
            p.setFont(font)
            fm = p.fontMetrics()
            tw2 = fm.horizontalAdvance(coord) + 10
            th2 = fm.height() + 6
            cx = mx + 15
            cy = my - 25
            if cx + tw2 > self.width():
                cx = mx - tw2 - 15
            if cy < 0:
                cy = my + 15
            p.setBrush(QBrush(QColor(20, 20, 20, 200)))
            p.setPen(QPen(QColor(80, 130, 220), 1))
            p.drawRoundedRect(cx, cy, tw2, th2, 3, 3)
            p.setPen(QColor(200, 200, 200))
            p.drawText(QRect(cx + 5, cy + 3, tw2 - 10, th2 - 6),
                       Qt.AlignmentFlag.AlignCenter, coord)

        p.end()

    # ── Annotation rendering ──

    def _paint_annotations(self, p: QPainter):
        for ann in self._annotations:
            self._render_annotation(p, ann)

    def _paint_current_annotation(self, p: QPainter):
        ann = AnnotationItem(
            tool=self._tool, color=self._color, width=self._pen_width,
            start=self._draw_start, end=self._draw_end,
            points=self._freehand_points, number=self._number_counter,
            blur_strength=self._blur_strength,
        )
        self._render_annotation(p, ann)

    def _render_annotation(self, p: QPainter, ann: AnnotationItem):
        pen = QPen(ann.color, ann.width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        s, e = ann.start, ann.end
        rect = QRect(s, e).normalized()

        if ann.tool == Tool.RECT:
            p.drawRect(rect)

        elif ann.tool == Tool.FILLED_RECT:
            fill = QColor(ann.color)
            fill.setAlpha(60)
            p.setBrush(QBrush(fill))
            p.drawRect(rect)

        elif ann.tool == Tool.ELLIPSE:
            p.drawEllipse(rect)

        elif ann.tool == Tool.LINE:
            p.drawLine(s, e)

        elif ann.tool == Tool.ARROW:
            self._draw_arrow(p, s, e, ann.color, ann.width)

        elif ann.tool == Tool.FREEHAND:
            if len(ann.points) > 1:
                for i in range(1, len(ann.points)):
                    p.drawLine(ann.points[i - 1], ann.points[i])

        elif ann.tool == Tool.TEXT:
            if ann.text:
                font = self._build_text_font(ann)
                p.setFont(font)
                p.setPen(ann.color)
                if ann.curved:
                    self._draw_curved_text(p, ann, font)
                else:
                    text_rect = QRect(s.x(), s.y(), 2000, 2000)
                    p.drawText(text_rect,
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                               ann.text)

        elif ann.tool == Tool.BLUR:
            self._draw_blur(p, rect, ann.blur_strength)

        elif ann.tool == Tool.HIGHLIGHT:
            highlight = QColor(ann.color)
            highlight.setAlpha(80)
            p.fillRect(rect, highlight)

        elif ann.tool == Tool.NUMBERED:
            self._draw_numbered(p, ann.start, ann.number, ann.color, ann.width,
                               ann.text_color)

    @staticmethod
    def _draw_arrow(p: QPainter, start: QPoint, end: QPoint,
                    color: QColor, width: int):
        p.setPen(QPen(color, width, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawLine(start, end)

        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            return
        dx /= length
        dy /= length

        head_len = min(20, length * 0.3)
        head_w = head_len * 0.5
        px = end.x() - dx * head_len
        py = end.y() - dy * head_len

        p1 = QPointF(px + dy * head_w, py - dx * head_w)
        p2 = QPointF(px - dy * head_w, py + dx * head_w)

        path = QPainterPath()
        path.moveTo(QPointF(end))
        path.lineTo(p1)
        path.lineTo(p2)
        path.closeSubpath()

        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)

    def _draw_blur(self, p: QPainter, rect: QRect, block: int = 8):
        if rect.width() < 2 or rect.height() < 2:
            return
        region = self._screenshot.copy(rect)
        tiny = region.scaled(
            max(1, rect.width() // block),
            max(1, rect.height() // block),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        blurred = tiny.scaled(
            rect.width(), rect.height(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        p.drawPixmap(rect.topLeft(), blurred)

    @staticmethod
    def _auto_contrast_color(bg: QColor) -> QColor:
        """Return black or white depending on background luminance."""
        lum = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
        return QColor(0, 0, 0) if lum > 140 else QColor(255, 255, 255)

    @staticmethod
    def _draw_numbered(p: QPainter, pos: QPoint, number: int,
                       color: QColor, width: int,
                       text_color: QColor = None):
        radius = max(14, width * 3)
        p.setBrush(QBrush(color))
        # Auto-contrast: dark text on bright bg, white text on dark bg
        if text_color:
            tc = text_color
        else:
            lum = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
            tc = QColor(0, 0, 0) if lum > 140 else QColor(255, 255, 255)
        p.setPen(QPen(tc, 2))
        p.drawEllipse(pos, radius, radius)
        font = QFont("Sans", max(10, radius - 4), QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(tc)
        p.drawText(QRect(pos.x() - radius, pos.y() - radius,
                         radius * 2, radius * 2),
                   Qt.AlignmentFlag.AlignCenter, str(number))

    # ── Mouse Events ──

    def _hit_test_annotation(self, pos: QPoint) -> int:
        """Return index of annotation under pos, or -1. Checks in reverse (top-most first)."""
        for i in range(len(self._annotations) - 1, -1, -1):
            ann = self._annotations[i]
            rect = self._annotation_bounds(ann)
            if rect.contains(pos):
                return i
        return -1

    def _annotation_bounds(self, ann: AnnotationItem) -> QRect:
        """Return the bounding rect of an annotation for hit testing."""
        if ann.tool == Tool.NUMBERED:
            radius = max(14, ann.width * 3)
            return QRect(ann.start.x() - radius, ann.start.y() - radius,
                         radius * 2, radius * 2)
        elif ann.tool == Tool.TEXT:
            font = self._build_text_font(ann)
            fm = QFontMetrics(font)
            if ann.curved:
                # Approximate bounding box for curved text
                radius = max(60, fm.horizontalAdvance(ann.text) * 0.55)
                cx, cy = ann.start.x() + int(radius), ann.start.y() + int(radius)
                return QRect(cx - int(radius) - 10, cy - int(radius) - 10,
                             int(radius) * 2 + 20, int(radius) * 2 + 20)
            text_rect = fm.boundingRect(
                QRect(ann.start.x(), ann.start.y(), 2000, 2000),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                ann.text,
            )
            return text_rect.adjusted(-4, -4, 4, 4)
        elif ann.tool == Tool.FREEHAND and ann.points:
            min_x = min(p.x() for p in ann.points)
            min_y = min(p.y() for p in ann.points)
            max_x = max(p.x() for p in ann.points)
            max_y = max(p.y() for p in ann.points)
            margin = max(6, ann.width)
            return QRect(min_x - margin, min_y - margin,
                         max_x - min_x + margin * 2, max_y - min_y + margin * 2)
        else:
            rect = QRect(ann.start, ann.end).normalized()
            margin = max(6, ann.width)
            return rect.adjusted(-margin, -margin, margin, margin)

    def deactivate(self):
        """Silently close this overlay (another screen was chosen)."""
        self._active = False
        self.hide()
        self.close()
        self.deleteLater()

    def mousePressEvent(self, event: QMouseEvent):
        if not self._active:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.overlay_activated.emit(self)

            # Fullscreen mode on multi-monitor: capture this screen immediately
            if self._mode == self.MODE_FULLSCREEN:
                self._capture_fullscreen()
                return

            pos = event.pos()

            # Check if clicking on an existing annotation to drag it
            hit_idx = self._hit_test_annotation(pos)
            if hit_idx >= 0 and self._tool == Tool.NONE:
                ann = self._annotations[hit_idx]
                self._dragging_ann = ann
                self._dragging_ann_idx = hit_idx
                self._drag_offset = pos - ann.start
                self._magnifier.hide()
                return

            if self._phase == self.PHASE_SELECT:
                if self._tool != Tool.NONE:
                    # Draw annotation on full screen
                    self._drawing = True
                    self._draw_start = pos
                    self._draw_end = pos
                    self._freehand_points = [pos]
                    self._magnifier.hide()
                else:
                    # Start region selection
                    self._selecting = True
                    self._sel_start = pos
                    self._sel_end = pos
                    self._sel_rect = QRect()
                    self._has_selection = False
                    self._magnifier.hide()
                    self.update()

            elif self._phase == self.PHASE_ANNOTATE:
                if self._tool != Tool.NONE:
                    self._drawing = True
                    self._draw_start = pos
                    self._draw_end = pos
                    self._freehand_points = [pos]

        elif event.button() == Qt.MouseButton.RightButton:
            if self._phase == self.PHASE_ANNOTATE:
                self._confirm()
            elif self._has_selection:
                self._has_selection = False
                self._sel_rect = QRect()
                self.update()
            else:
                self._cancel()

    def mouseMoveEvent(self, event: QMouseEvent):
        self._mouse_pos = event.pos()

        # Dragging an existing annotation
        if self._dragging_ann is not None:
            new_start = event.pos() - self._drag_offset
            delta = new_start - self._dragging_ann.start
            self._dragging_ann.start += delta
            self._dragging_ann.end += delta
            if self._dragging_ann.points:
                self._dragging_ann.points = [
                    QPoint(p.x() + delta.x(), p.y() + delta.y())
                    for p in self._dragging_ann.points
                ]
            self.update()
            return

        # Update hover state when not drawing/dragging (for DEL-to-delete)
        if not self._drawing and not self._selecting:
            old = self._hovered_ann_idx
            self._hovered_ann_idx = self._hit_test_annotation(event.pos())
            if self._hovered_ann_idx != old:
                self.update()

        # Drawing annotation (works in both PHASE_SELECT and PHASE_ANNOTATE)
        if self._drawing:
            self._draw_end = event.pos()
            if self._tool == Tool.FREEHAND:
                self._freehand_points.append(event.pos())
            self.update()

        elif self._phase == self.PHASE_SELECT and self._selecting:
            self._sel_end = event.pos()
            self._sel_rect = QRect(self._sel_start, self._sel_end).normalized()
            self._has_selection = True
            self.update()

        elif self._phase == self.PHASE_SELECT and not self._selecting:
            self._magnifier.update_position(event.pos())
            if not self._magnifier.isVisible():
                self._magnifier.show()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Finish dragging an annotation
        if self._dragging_ann is not None:
            self._dragging_ann = None
            self._dragging_ann_idx = -1
            self._drag_offset = QPoint()
            self.update()
            return

        if self._phase == self.PHASE_SELECT and self._selecting:
            self._selecting = False
            self._sel_end = event.pos()
            self._sel_rect = QRect(self._sel_start, self._sel_end).normalized()

            if self._sel_rect.width() < 5 or self._sel_rect.height() < 5:
                self._has_selection = False
                self._sel_rect = QRect()
                self.update()
                return

            self._has_selection = True
            # Region selected → finish immediately (annotations included)
            self._finish_capture()

        elif self._drawing:
            # Commit annotation (works in both PHASE_SELECT and PHASE_ANNOTATE)
            self._drawing = False

            if self._tool == Tool.TEXT:
                self._commit_text_annotation()
            elif self._tool == Tool.NUMBERED:
                ann = AnnotationItem(
                    self._tool, self._color, self._pen_width,
                    self._draw_start, self._draw_end,
                    number=self._number_counter,
                )
                self._annotations.append(ann)
                self._number_counter += 1
            elif self._tool == Tool.BLUR:
                ann = AnnotationItem(
                    self._tool, self._color, self._pen_width,
                    self._draw_start, self._draw_end,
                    blur_strength=self._blur_strength,
                )
                self._annotations.append(ann)
            else:
                ann = AnnotationItem(
                    self._tool, self._color, self._pen_width,
                    self._draw_start, self._draw_end,
                    points=self._freehand_points,
                )
                self._annotations.append(ann)

            self._freehand_points = []
            self.update()

    def _commit_text_annotation(self):
        dlg = TextFormatDialog(self, initial_color=self._color)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.result_data()
            if data["text"]:
                ann = AnnotationItem(
                    Tool.TEXT, self._color, self._pen_width,
                    self._draw_start, self._draw_start, text=data["text"],
                    font_family=data["font_family"],
                    font_size=data["font_size"],
                    bold=data["bold"],
                    italic=data["italic"],
                    curved=data["curved"],
                )
                self._annotations.append(ann)
        self.update()

    @staticmethod
    def _build_text_font(ann: AnnotationItem) -> QFont:
        """Construct QFont from annotation formatting properties."""
        size = ann.font_size if ann.font_size > 0 else max(12, ann.width * 4)
        font = QFont(ann.font_family, size)
        font.setBold(ann.bold)
        font.setItalic(ann.italic)
        return font

    def _draw_curved_text(self, p: QPainter, ann: AnnotationItem, font: QFont):
        """Draw text along a circular arc starting from ann.start."""
        fm = QFontMetrics(font)
        total_w = fm.horizontalAdvance(ann.text)
        radius = max(60, total_w * 0.55)

        cx = ann.start.x() + radius
        cy = ann.start.y() + radius

        # Start angle (top of arc, going clockwise)
        arc_len = total_w / radius  # in radians
        start_angle = math.pi / 2 + arc_len / 2  # center the text at the top

        angle = start_angle
        p.save()
        for ch in ann.text:
            char_w = fm.horizontalAdvance(ch)
            x = cx + radius * math.cos(angle)
            y = cy - radius * math.sin(angle)
            p.save()
            p.translate(x, y)
            p.rotate(-math.degrees(angle) + 90)
            p.setFont(font)
            p.setPen(ann.color)
            p.drawText(0, 0, ch)
            p.restore()
            angle -= char_w / radius
        p.restore()

    def _paint_drag_highlight(self, p: QPainter):
        """Draw a highlight border around the annotation being dragged."""
        if self._dragging_ann is None:
            return
        rect = self._annotation_bounds(self._dragging_ann)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(0, 180, 255, 180), 2, Qt.PenStyle.DashLine))
        p.drawRoundedRect(rect, 4, 4)

    def _paint_hover_highlight(self, p: QPainter):
        """Draw a red-tinted border + DEL hint around the hovered annotation."""
        if self._hovered_ann_idx < 0 or self._hovered_ann_idx >= len(self._annotations):
            return
        ann = self._annotations[self._hovered_ann_idx]
        rect = self._annotation_bounds(ann)
        # Dashed red border
        p.setBrush(QBrush(QColor(255, 60, 60, 25)))
        p.setPen(QPen(QColor(255, 80, 80, 200), 1.5, Qt.PenStyle.DashLine))
        p.drawRoundedRect(rect, 4, 4)
        # DEL hint label
        font = QFont("Sans", 8)
        p.setFont(font)
        fm = p.fontMetrics()
        label = "DEL"
        lw = fm.horizontalAdvance(label) + 8
        lh = fm.height() + 4
        lx = rect.right() - lw + 2
        ly = rect.top() - lh - 2
        if ly < 0:
            ly = rect.bottom() + 2
        if lx + lw > self.width():
            lx = rect.left()
        p.setBrush(QBrush(QColor(200, 40, 40, 220)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(lx, ly, lw, lh, 3, 3)
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRect(lx, ly, lw, lh), Qt.AlignmentFlag.AlignCenter, label)

    # ── Keyboard ──

    def keyPressEvent(self, event: QKeyEvent):
        if not self._active:
            return
        key = event.key()
        mods = event.modifiers()

        if key == Qt.Key.Key_Escape:
            if self._dragging_ann is not None:
                self._dragging_ann = None
                self._dragging_ann_idx = -1
                self.update()
            elif self._phase == self.PHASE_ANNOTATE:
                if self._annotations:
                    self._confirm()
                else:
                    self._phase = self.PHASE_SELECT
                    self.update()
            elif self._has_selection:
                self._has_selection = False
                self._sel_rect = QRect()
                self.update()
            else:
                self._cancel()

        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._has_selection:
                self._confirm()
            else:
                self._capture_fullscreen()

        elif key == Qt.Key.Key_F and self._phase == self.PHASE_SELECT:
            self._capture_fullscreen()

        # Annotation tool shortcuts
        elif key == Qt.Key.Key_A:
            self._toolbar.select_tool(Tool.ARROW)
        elif key == Qt.Key.Key_R:
            self._toolbar.select_tool(Tool.RECT)
        elif key == Qt.Key.Key_E:
            self._toolbar.select_tool(Tool.ELLIPSE)
        elif key == Qt.Key.Key_L:
            self._toolbar.select_tool(Tool.LINE)
        elif key == Qt.Key.Key_D:
            self._toolbar.select_tool(Tool.FREEHAND)
        elif key == Qt.Key.Key_B:
            self._toolbar.select_tool(Tool.BLUR)
        elif key == Qt.Key.Key_H:
            self._toolbar.select_tool(Tool.HIGHLIGHT)
        elif key == Qt.Key.Key_N:
            self._toolbar.select_tool(Tool.NUMBERED)
        elif key == Qt.Key.Key_C:
            self._toolbar._pick_color()

        # Delete hovered annotation
        elif key == Qt.Key.Key_Delete:
            if self._hovered_ann_idx >= 0 and self._hovered_ann_idx < len(self._annotations):
                self._annotations.pop(self._hovered_ann_idx)
                self._hovered_ann_idx = self._hit_test_annotation(self._mouse_pos)
                self.update()

        # Undo
        elif key == Qt.Key.Key_Z and (mods & Qt.KeyboardModifier.ControlModifier):
            self._undo()

    # ── Actions ──

    def _undo(self):
        if self._annotations:
            removed = self._annotations.pop()
            if removed.tool == Tool.NUMBERED:
                self._number_counter = max(1, self._number_counter - 1)
            self.update()

    def _confirm(self):
        if self._has_selection:
            self._finish_capture()
        else:
            self._capture_fullscreen()

    def _finish_capture(self):
        """Finalize: compose the selected region + annotations → emit."""
        sel = self._sel_rect.normalized()
        if sel.width() < 1 or sel.height() < 1:
            self._capture_fullscreen()
            return

        result = self._screenshot.copy(sel)

        if self._annotations:
            p = QPainter(result)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.translate(-sel.x(), -sel.y())
            self._paint_annotations(p)
            p.end()

        self.hide()
        self.capture_completed.emit(result)

    def _capture_fullscreen(self):
        if not self._active:
            return
        self.overlay_activated.emit(self)
        self.hide()
        self.capture_completed.emit(self._screenshot.copy())

    def _cancel(self):
        if not self._active:
            return
        self.overlay_activated.emit(self)
        self.hide()
        self.capture_cancelled.emit()


# ─── Screenshot Grab ─────────────────────────────────────────────────────────

def _is_flatpak() -> bool:
    """Detect if we're running inside a Flatpak sandbox."""
    return (
        os.path.isfile("/.flatpak-info")
        or "FLATPAK_ID" in os.environ
        or os.environ.get("container") == "flatpak"
        or any(p.startswith("/app/") for p in
               os.environ.get("PATH", "").split(":"))
    )


def grab_screenshot_via_portal() -> QPixmap | None:
    """Take a fullscreen screenshot.

    On macOS, uses screencapture. On Linux, tries XDG Desktop Portal first,
    then CLI tools, then QScreen.grabWindow as fallback.
    Handles Flatpak sandboxes by using flatpak-spawn --host.
    Returns a QPixmap of the entire screen, or None on failure.
    """
    import sys as _sys
    if _sys.platform == "darwin":
        # macOS: use screencapture
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        try:
            subprocess.run(
                ["screencapture", "-x", tmp.name],
                capture_output=True, timeout=10, check=True,
            )
            pixmap = QPixmap(tmp.name)
            if not pixmap.isNull():
                return pixmap
        except (subprocess.SubprocessError, OSError):
            pass
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
        # Fallback: QScreen grab
        screen = QGuiApplication.primaryScreen()
        if screen:
            pixmap = screen.grabWindow(0)
            if not pixmap.isNull():
                return pixmap
        return None

    helper = os.path.join(os.path.dirname(__file__), "_portal_helper.py")
    in_flatpak = _is_flatpak()

    # Strategy 1: Portal helper via host Python
    if os.path.exists(helper):
        for attempt_host in ([True, False] if in_flatpak else [False, True]):
            try:
                if attempt_host and shutil.which("flatpak-spawn"):
                    cmd = ["flatpak-spawn", "--host", "python3",
                           helper, "screenshot", "--fullscreen"]
                else:
                    import sys
                    cmd = [sys.executable, helper, "screenshot", "--fullscreen"]

                r = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30,
                )
                if r.returncode == 0 and r.stdout.strip():
                    path = r.stdout.strip()
                    if os.path.isfile(path):
                        pixmap = QPixmap(path)
                        if not pixmap.isNull():
                            return pixmap
            except (subprocess.SubprocessError, OSError):
                continue

    # Strategy 2: CLI tools
    tool_commands = []
    for tool, args_fn in [
        ("grim", lambda tmp: ["grim", tmp]),
        ("gnome-screenshot", lambda tmp: ["gnome-screenshot", "-f", tmp]),
        ("scrot", lambda tmp: ["scrot", tmp]),
    ]:
        if shutil.which(tool):
            tool_commands.append((False, tool, args_fn))
        elif in_flatpak:
            tool_commands.append((True, tool, args_fn))

    for use_host, tool, args_fn in tool_commands:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        try:
            cmd = args_fn(tmp.name)
            if use_host and shutil.which("flatpak-spawn"):
                cmd = ["flatpak-spawn", "--host"] + cmd
            subprocess.run(cmd, capture_output=True, timeout=10, check=True)
            pixmap = QPixmap(tmp.name)
            if not pixmap.isNull():
                return pixmap
        except (subprocess.SubprocessError, OSError):
            pass
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    # Strategy 3: QScreen grab (X11 only)
    screen = QGuiApplication.primaryScreen()
    if screen:
        pixmap = screen.grabWindow(0)
        if not pixmap.isNull():
            return pixmap

    return None
