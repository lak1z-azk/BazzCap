"""Capture history tracker for BazzCap."""

import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict, field


HISTORY_FILE = os.path.expanduser("~/.config/bazzcap/history.json")


@dataclass
class HistoryEntry:
    filepath: str
    timestamp: str
    capture_type: str  # "screenshot", "recording", "gif"
    mode: str = ""     # "fullscreen", "region", "window"
    file_size: int = 0
    thumbnail: str = ""

    @staticmethod
    def create(filepath, capture_type, mode=""):
        size = 0
        try:
            size = os.path.getsize(filepath)
        except OSError:
            pass
        return HistoryEntry(
            filepath=filepath,
            timestamp=datetime.now().isoformat(),
            capture_type=capture_type,
            mode=mode,
            file_size=size,
        )


class HistoryManager:
    """Manage capture history."""

    def __init__(self, max_entries=500):
        self._entries: list[HistoryEntry] = []
        self._max = max_entries
        self.load()

    def load(self):
        """Load history from disk."""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    data = json.load(f)
                self._entries = [HistoryEntry(**e) for e in data]
            except (json.JSONDecodeError, IOError, TypeError):
                self._entries = []

    def save(self):
        """Save history to disk."""
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "w") as f:
            json.dump([asdict(e) for e in self._entries], f, indent=2)

    def add(self, entry: HistoryEntry):
        """Add a new history entry."""
        self._entries.insert(0, entry)
        if len(self._entries) > self._max:
            self._entries = self._entries[:self._max]
        self.save()

    @property
    def entries(self) -> list[HistoryEntry]:
        return list(self._entries)

    def clear(self):
        self._entries.clear()
        self.save()

    def remove(self, filepath: str):
        self._entries = [e for e in self._entries if e.filepath != filepath]
        self.save()
