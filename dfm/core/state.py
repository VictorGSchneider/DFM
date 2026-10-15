"""Remember which dotfiles the user switched off, across runs."""

import json
import os
import tempfile
from pathlib import Path


def _state_file() -> Path:
    return Path.home() / ".local" / "share" / "dfm" / "state.json"


def _load_disabled() -> set[str]:
    """Paths switched off earlier; anything unreadable counts as none."""
    try:
        with open(_state_file(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return set()
    disabled = data.get("disabled") if isinstance(data, dict) else None
    if not isinstance(disabled, list):
        return set()
    return {p for p in disabled if isinstance(p, str)}


def apply_saved_enabled(entries: list) -> None:
    """Switch off the entries the user switched off in an earlier run."""
    disabled = _load_disabled()
    for entry in entries:
        if entry.path in disabled:
            entry.enabled = False


def remember_enabled(entries: list) -> None:
    """Save the current choices (only touches the disk if they changed)."""
    saved = _load_disabled()
    scanned = {e.path for e in entries}
    # A dotfile that isn't on disk right now keeps whatever was saved for it
    disabled = (saved - scanned) | {e.path for e in entries if not e.enabled}
    if disabled == saved:
        return

    target = _state_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".state-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"disabled": sorted(disabled)}, f, indent=2)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
