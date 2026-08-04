#!/usr/bin/env python3
"""Self-check for the 1.3.1 cleanup. Run: python3 test_cleanup.py"""

import os
import sys

from bazzcap import capture, clipboard, config, history, overlay, runtime


def test_config_dir_single_source():
    """All config paths route through runtime.config_dir()."""
    d = runtime.config_dir()
    assert d.endswith("bazzcap"), d
    assert config.CONFIG_DIR == d
    assert config.CONFIG_FILE == os.path.join(d, "config.json")
    assert history.HISTORY_FILE == os.path.join(d, "history.json")


def test_no_duplicate_flatpak_helper():
    """overlay uses the shared is_flatpak, not a private copy."""
    assert not hasattr(overlay, "_is_flatpak")
    assert overlay.is_flatpak is runtime.is_flatpak
    assert isinstance(runtime.is_flatpak(), bool)


def test_embedded_helper_gone():
    """The inlined helper copy and its gdbus tier are removed."""
    for name in ("_PORTAL_HELPER_SOURCE", "_embedded_helper_path",
                 "_gdbus_portal_screenshot", "_EMBEDDED_HELPER_MARKER"):
        assert not hasattr(capture, name), name


def test_portal_returns_none_when_helper_missing(tmp="/nonexistent/helper/dir"):
    """_portal_screenshot degrades to None rather than raising."""
    orig = capture.packaged_script_path
    capture.packaged_script_path = lambda n: os.path.join(tmp, n)
    try:
        assert capture._portal_screenshot(interactive=False) is None
    finally:
        capture.packaged_script_path = orig


def test_dead_sound_helpers_gone():
    from bazzcap import app
    for name in ("_mute_event_sounds", "_restore_event_sounds"):
        assert not hasattr(app, name), name
        assert not hasattr(app.MainWindow, name), name


def test_dead_config_keys_gone():
    for key in ("jpeg_quality", "show_notification"):
        assert key not in config.DEFAULT_CONFIG, key
    # keys still read by app.py must survive
    for key in ("start_minimized", "theme", "show_magnifier", "image_format"):
        assert key in config.DEFAULT_CONFIG, key


def test_clipboard_rejects_missing_file():
    assert clipboard.copy_image_to_clipboard("/nonexistent/x.png") is False
    assert not hasattr(clipboard, "_has")


def test_backends_probe_runs():
    backends = capture.detect_available_backends()
    assert isinstance(backends, list)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} checks passed")
