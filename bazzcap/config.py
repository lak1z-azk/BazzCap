"""Configuration management for BazzCap."""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

IS_MACOS = sys.platform == "darwin"

# --- Platform-specific defaults ---
if IS_MACOS:
    _DEFAULT_HOTKEYS = {
        "capture_fullscreen": "<Super><Shift>1",
        "capture_region": "<Super><Shift>2",
        "capture_window": "<Super><Shift>w",
    }
    _CONFIG_DIR = os.path.expanduser("~/Library/Application Support/bazzcap")
else:
    _DEFAULT_HOTKEYS = {
        "capture_fullscreen": "Print",
        "capture_region": "<Ctrl>Print",
        "capture_window": "<Alt>Print",
    }
    _CONFIG_DIR = os.path.expanduser("~/.config/bazzcap")


DEFAULT_CONFIG = {
    "save_directory": os.path.expanduser("~/Pictures/BazzCap"),
    "filename_pattern": "BazzCap_%Y-%m-%d_%H-%M-%S",
    "auto_copy_to_clipboard": True,
    "open_editor_after_capture": True,
    "show_notification": True,
    "image_format": "png",
    "jpeg_quality": 95,

    "hotkeys": dict(_DEFAULT_HOTKEYS),
    "editor": {
        "default_color": "#FF0000",
        "default_line_width": 3,
        "default_font_size": 16,
        "blur_radius": 15,
        "highlight_opacity": 0.35,
    },
    "minimize_to_tray": True,
    "start_minimized": True,
    "start_with_system": True,
    "theme": "system",
}

CONFIG_DIR = _CONFIG_DIR
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.json")


class Config:
    """Application configuration manager."""

    def __init__(self):
        self._config = dict(DEFAULT_CONFIG)
        self._ensure_dirs()
        self.load()

    def _ensure_dirs(self):
        """Ensure config and save directories exist."""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(self._config["save_directory"], exist_ok=True)

    def load(self):
        """Load config from disk, merging with defaults."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved = json.load(f)
                self._deep_merge(self._config, saved)
            except (json.JSONDecodeError, IOError):
                pass
        self._ensure_dirs()

    def save(self):
        """Persist config to disk."""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._config, f, indent=2)

    def get(self, key, default=None):
        """Get a config value (supports dot notation: 'editor.default_color')."""
        keys = key.split(".")
        val = self._config
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
            if val is None:
                return default
        return val

    def set(self, key, value):
        """Set a config value (supports dot notation)."""
        keys = key.split(".")
        d = self._config
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value
        self.save()

    @property
    def save_directory(self):
        return self._config["save_directory"]

    @property
    def data(self):
        return self._config

    def generate_filename(self, extension=None):
        """Generate a timestamped filename."""
        if extension is None:
            extension = self._config["image_format"]
        pattern = self._config["filename_pattern"]
        name = datetime.now().strftime(pattern)
        return f"{name}.{extension}"

    def generate_filepath(self, extension=None):
        """Generate a full file path for a new capture."""
        filename = self.generate_filename(extension)
        return os.path.join(self._config["save_directory"], filename)

    @staticmethod
    def _deep_merge(base, override):
        """Deep merge override dict into base dict."""
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                Config._deep_merge(base[k], v)
            else:
                base[k] = v
