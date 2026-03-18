"""Notes and tags storage per dotfile."""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field


NOTES_FILE = Path.home() / ".local" / "share" / "dfm" / "notes.json"


@dataclass
class DotfileNote:
    """Notes and tags for a dotfile."""
    name: str
    note: str = ""
    tags: list[str] = field(default_factory=list)
    favorite: bool = False


def _ensure_dir() -> None:
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_all() -> dict[str, dict]:
    if not NOTES_FILE.is_file():
        return {}
    try:
        with open(NOTES_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: dict[str, dict]) -> None:
    _ensure_dir()
    with open(NOTES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_note(name: str) -> DotfileNote:
    """Get notes/tags for a dotfile."""
    data = _load_all()
    entry = data.get(name, {})
    return DotfileNote(
        name=name,
        note=entry.get("note", ""),
        tags=entry.get("tags", []),
        favorite=entry.get("favorite", False),
    )


def save_note(note: DotfileNote) -> None:
    """Save notes/tags for a dotfile."""
    data = _load_all()
    data[note.name] = {
        "note": note.note,
        "tags": note.tags,
        "favorite": note.favorite,
    }
    _save_all(data)


def set_favorite(name: str, favorite: bool) -> None:
    """Toggle favorite status."""
    note = get_note(name)
    note.favorite = favorite
    save_note(note)


def get_favorites() -> list[str]:
    """Get names of all favorited dotfiles."""
    data = _load_all()
    return [name for name, info in data.items()
            if info.get("favorite", False)]


def add_tag(name: str, tag: str) -> None:
    """Add a tag to a dotfile."""
    note = get_note(name)
    if tag not in note.tags:
        note.tags.append(tag)
        save_note(note)


def remove_tag(name: str, tag: str) -> None:
    """Remove a tag from a dotfile."""
    note = get_note(name)
    if tag in note.tags:
        note.tags.remove(tag)
        save_note(note)


def get_all_tags() -> list[str]:
    """Get all unique tags used across dotfiles."""
    data = _load_all()
    tags = set()
    for info in data.values():
        tags.update(info.get("tags", []))
    return sorted(tags)


def search_by_tag(tag: str) -> list[str]:
    """Find dotfile names that have a specific tag."""
    data = _load_all()
    return [name for name, info in data.items()
            if tag in info.get("tags", [])]
