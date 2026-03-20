"""Auto-backup system - snapshot dotfiles before edits."""

import os
import json
import shutil
import time
from pathlib import Path
from dataclasses import dataclass, field


BACKUP_DIR = Path.home() / ".local" / "share" / "dfm" / "backups"
MAX_BACKUPS_PER_FILE = 50


@dataclass
class BackupEntry:
    """A single backup snapshot."""
    file_path: str
    backup_path: str
    timestamp: float
    size: int
    reason: str = "edit"

    @property
    def display_time(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S",
                             time.localtime(self.timestamp))

    @property
    def relative_age(self) -> str:
        delta = time.time() - self.timestamp
        if delta < 60:
            return "just now"
        if delta < 3600:
            return f"{int(delta / 60)}m ago"
        if delta < 86400:
            return f"{int(delta / 3600)}h ago"
        return f"{int(delta / 86400)}d ago"


def ensure_backup_dir() -> Path:
    """Create backup directory if needed."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def create_backup(file_path: str, reason: str = "edit") -> BackupEntry | None:
    """Create a backup snapshot of a file before editing."""
    if not os.path.isfile(file_path):
        return None

    ensure_backup_dir()

    # Create a subdirectory structure mirroring the original path
    rel = os.path.relpath(file_path, str(Path.home()))
    safe_name = rel.replace(os.sep, "__")
    file_backup_dir = BACKUP_DIR / safe_name
    file_backup_dir.mkdir(parents=True, exist_ok=True)

    ts = time.time()
    ts_str = time.strftime("%Y%m%d_%H%M%S", time.localtime(ts))
    basename = os.path.basename(file_path)
    backup_name = f"{basename}.{ts_str}.bak"
    backup_path = file_backup_dir / backup_name

    shutil.copy2(file_path, backup_path)

    entry = BackupEntry(
        file_path=file_path,
        backup_path=str(backup_path),
        timestamp=ts,
        size=os.path.getsize(file_path),
        reason=reason,
    )

    # Write metadata
    _save_metadata(file_backup_dir, entry)

    # Prune old backups
    _prune_backups(file_backup_dir)

    return entry


def get_backups(file_path: str) -> list[BackupEntry]:
    """Get all backups for a specific file."""
    rel = os.path.relpath(file_path, str(Path.home()))
    safe_name = rel.replace(os.sep, "__")
    file_backup_dir = BACKUP_DIR / safe_name

    if not file_backup_dir.is_dir():
        return []

    meta_path = file_backup_dir / "metadata.json"
    if not meta_path.is_file():
        return []

    try:
        with open(meta_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    entries = []
    for item in data.get("backups", []):
        if os.path.isfile(item.get("backup_path", "")):
            entries.append(BackupEntry(
                file_path=item["file_path"],
                backup_path=item["backup_path"],
                timestamp=item["timestamp"],
                size=item.get("size", 0),
                reason=item.get("reason", "edit"),
            ))

    entries.sort(key=lambda e: e.timestamp, reverse=True)
    return entries


def restore_backup(backup: BackupEntry) -> bool:
    """Restore a backup, backing up current file first."""
    if not os.path.isfile(backup.backup_path):
        return False

    # Backup current before restoring
    if os.path.isfile(backup.file_path):
        create_backup(backup.file_path, reason="pre-restore")

    shutil.copy2(backup.backup_path, backup.file_path)
    return True


def get_diff(file_path: str, backup: BackupEntry) -> str:
    """Get a unified diff between current file and a backup."""
    import difflib

    if not os.path.isfile(file_path) or not os.path.isfile(backup.backup_path):
        return ""

    try:
        with open(backup.backup_path) as f:
            old_lines = f.readlines()
        with open(file_path) as f:
            new_lines = f.readlines()
    except OSError:
        return ""

    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"backup ({backup.display_time})",
        tofile="current",
    )
    return "".join(diff)


def _save_metadata(backup_dir: Path, entry: BackupEntry) -> None:
    """Save or update backup metadata."""
    meta_path = backup_dir / "metadata.json"
    data = {"backups": []}
    if meta_path.is_file():
        try:
            with open(meta_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {"backups": []}

    data["backups"].append({
        "file_path": entry.file_path,
        "backup_path": entry.backup_path,
        "timestamp": entry.timestamp,
        "size": entry.size,
        "reason": entry.reason,
    })

    with open(meta_path, "w") as f:
        json.dump(data, f, indent=2)


def _prune_backups(backup_dir: Path) -> None:
    """Remove oldest backups beyond the limit."""
    meta_path = backup_dir / "metadata.json"
    if not meta_path.is_file():
        return

    try:
        with open(meta_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    backups = data.get("backups", [])
    if len(backups) <= MAX_BACKUPS_PER_FILE:
        return

    backups.sort(key=lambda b: b.get("timestamp", 0), reverse=True)
    keep = backups[:MAX_BACKUPS_PER_FILE]
    remove = backups[MAX_BACKUPS_PER_FILE:]

    for item in remove:
        path = item.get("backup_path", "")
        if os.path.isfile(path):
            os.remove(path)

    data["backups"] = keep
    with open(meta_path, "w") as f:
        json.dump(data, f, indent=2)
