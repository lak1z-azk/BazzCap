import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime

if sys.platform == "darwin":
    HISTORY_FILE = os.path.expanduser("~/Library/Application Support/bazzcap/history.json")
else:
    HISTORY_FILE = os.path.expanduser("~/.config/bazzcap/history.json")

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


@dataclass
class HistoryEntry:
    filepath: str
    timestamp: str
    capture_type: str
    mode: str = ""
    file_size: int = 0
    thumbnail: str = ""

    @staticmethod
    def create(filepath: str, capture_type: str, mode: str = "", timestamp: str | None = None):
        size = 0
        try:
            size = os.path.getsize(filepath)
        except OSError:
            pass
        return HistoryEntry(
            filepath=filepath,
            timestamp=timestamp or datetime.now().isoformat(),
            capture_type=capture_type,
            mode=mode,
            file_size=size,
        )


class HistoryManager:

    def __init__(self, max_entries: int = 500):
        self._entries: list[HistoryEntry] = []
        self._max = max_entries
        self.load()

    def load(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    data = json.load(f)
                self._entries = [HistoryEntry(**entry) for entry in data]
            except (json.JSONDecodeError, IOError, TypeError):
                self._entries = []

    def save(self):
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "w") as f:
            json.dump([asdict(entry) for entry in self._entries], f, indent=2)

    def add(self, entry: HistoryEntry):
        self._entries = [existing for existing in self._entries if existing.filepath != entry.filepath]
        self._entries.insert(0, entry)
        if len(self._entries) > self._max:
            self._entries = self._entries[:self._max]
        self.save()

    def sync_with_directory(self, directory: str, max_scan: int = 200) -> bool:
        if not directory or not os.path.isdir(directory):
            return False

        changed = False
        known = {entry.filepath for entry in self._entries}
        discovered: list[HistoryEntry] = []

        try:
            candidates = []
            for name in os.listdir(directory):
                path = os.path.join(directory, name)
                if not os.path.isfile(path):
                    continue
                if os.path.splitext(name)[1].lower() not in _IMAGE_EXTENSIONS:
                    continue
                try:
                    stat = os.stat(path)
                except OSError:
                    continue
                candidates.append((stat.st_mtime, path, stat.st_size))
        except OSError:
            return False

        candidates.sort(reverse=True)
        for mtime, path, size in candidates[:max_scan]:
            if path in known:
                continue
            discovered.append(
                HistoryEntry(
                    filepath=path,
                    timestamp=datetime.fromtimestamp(mtime).isoformat(),
                    capture_type="screenshot",
                    mode="",
                    file_size=size,
                )
            )
            known.add(path)

        if discovered:
            self._entries = discovered + self._entries
            self._entries.sort(key=lambda entry: entry.timestamp, reverse=True)
            self._entries = self._entries[:self._max]
            self.save()
            changed = True

        return changed

    @property
    def entries(self) -> list[HistoryEntry]:
        return list(self._entries)

    def clear(self):
        self._entries.clear()
        self.save()

    def remove(self, filepath: str):
        self._entries = [entry for entry in self._entries if entry.filepath != filepath]
        self.save()
