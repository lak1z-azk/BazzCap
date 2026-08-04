#!/usr/bin/env python3
"""Click-vs-drag capture check. Run: QT_QPA_PLATFORM=offscreen python3 test_click_fullscreen.py"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QColor, QPainter
from PyQt6.QtCore import QPoint, QRect, Qt

app = QApplication([])

from bazzcap.overlay import RegionCaptureOverlay, AnnotationItem, Tool


def make_overlay():
    """Overlay over a 400x300 red screenshot, no real screen needed."""
    shot = QPixmap(400, 300)
    shot.fill(QColor("red"))
    ov = RegionCaptureOverlay.__new__(RegionCaptureOverlay)
    ov._screenshot = shot
    ov._annotations = []
    ov._active = True
    ov._sel_rect = QRect()
    ov.hide = lambda: None
    ov.overlay_activated = type("S", (), {"emit": lambda *a: None})()
    captured = []
    ov.capture_completed = type("S", (), {"emit": lambda self, px: captured.append(px)})()
    return ov, captured


def blue_line_annotation():
    return AnnotationItem(Tool.LINE, QColor("blue"), 20, QPoint(10, 10), QPoint(200, 10))


def test_click_captures_full_screen():
    ov, captured = make_overlay()
    ov._capture_fullscreen()
    assert len(captured) == 1
    assert captured[0].size() == ov._screenshot.size(), captured[0].size()


def test_fullscreen_includes_annotations():
    """The whole point: a click-capture must burn in annotations."""
    ov, captured = make_overlay()
    ov._annotations = [blue_line_annotation()]
    ov._capture_fullscreen()

    img = captured[0].toImage()
    # Somewhere along the drawn line the pixel must no longer be pure red.
    drawn = any(QColor(img.pixel(x, 10)).blue() > 100 for x in range(20, 190))
    assert drawn, "annotations were not composited into the fullscreen capture"


def test_region_still_crops():
    ov, captured = make_overlay()
    ov._sel_rect = QRect(50, 40, 120, 90)
    ov._paint_annotations = lambda p: None
    ov._finish_capture()
    assert captured[0].size().width() == 120
    assert captured[0].size().height() == 90


def test_degenerate_region_falls_back_to_fullscreen():
    ov, captured = make_overlay()
    ov._sel_rect = QRect(10, 10, 0, 0)
    ov._finish_capture()
    assert captured[0].size() == ov._screenshot.size()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} checks passed")
