"""File change monitor - watches dotfiles for external modifications."""

import os
import time
import threading
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileState:
    """Tracked state of a file."""
    path: str
    mtime: float
    size: int


class DotfileMonitor:
    """Watches dotfile config files for external changes."""

    def __init__(self, poll_interval: float = 3.0):
        self._tracked: dict[str, FileState] = {}
        self._callbacks: list = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._poll_interval = poll_interval
        self._lock = threading.Lock()

    def track(self, file_path: str) -> None:
        """Start tracking a file."""
        with self._lock:
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                self._tracked[file_path] = FileState(
                    path=file_path,
                    mtime=stat.st_mtime,
                    size=stat.st_size,
                )

    def untrack(self, file_path: str) -> None:
        """Stop tracking a file."""
        with self._lock:
            self._tracked.pop(file_path, None)

    def track_entries(self, entries: list) -> None:
        """Track all DotfileEntry objects."""
        for entry in entries:
            config_path = entry.get_config_path()
            if config_path:
                self.track(config_path)

    def on_change(self, callback) -> None:
        """Register a callback for file changes.

        Callback receives (file_path: str, change_type: str).
        change_type is one of: "modified", "deleted", "created".
        """
        self._callbacks.append(callback)

    def start(self) -> None:
        """Start the monitor thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the monitor thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def check_now(self) -> list[tuple[str, str]]:
        """Immediately check for changes. Returns list of (path, change_type)."""
        changes = []
        with self._lock:
            for path, state in list(self._tracked.items()):
                if not os.path.isfile(path):
                    if state.mtime > 0:
                        changes.append((path, "deleted"))
                        state.mtime = 0
                        state.size = 0
                    continue

                try:
                    stat = os.stat(path)
                except OSError:
                    continue

                if stat.st_mtime != state.mtime or stat.st_size != state.size:
                    changes.append((path, "modified"))
                    state.mtime = stat.st_mtime
                    state.size = stat.st_size

        return changes

    def update_state(self, file_path: str) -> None:
        """Update tracked state after we've made our own changes."""
        with self._lock:
            if file_path in self._tracked and os.path.isfile(file_path):
                stat = os.stat(file_path)
                self._tracked[file_path] = FileState(
                    path=file_path,
                    mtime=stat.st_mtime,
                    size=stat.st_size,
                )

    def _poll_loop(self) -> None:
        """Background polling loop."""
        while self._running:
            changes = self.check_now()
            for path, change_type in changes:
                for cb in self._callbacks:
                    try:
                        cb(path, change_type)
                    except Exception:
                        pass
            time.sleep(self._poll_interval)
