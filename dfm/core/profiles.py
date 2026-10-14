"""Profile system - save/load dotfile configuration sets."""

import hashlib
import os
import json
import shutil
import time
from pathlib import Path
from dataclasses import dataclass, field as datafield


PROFILES_DIR = Path.home() / ".local" / "share" / "dfm" / "profiles"


@dataclass
class Profile:
    """A saved configuration profile."""
    name: str
    description: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    entries: dict[str, dict] = datafield(default_factory=dict)
    # entries maps dotfile name -> {enabled: bool, config_snapshot: str|None}

    @property
    def display_time(self) -> str:
        ts = self.updated_at or self.created_at
        if ts:
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        return "unknown"

    @property
    def dotfile_count(self) -> int:
        return len(self.entries)

    @property
    def enabled_count(self) -> int:
        return sum(1 for e in self.entries.values() if e.get("enabled"))


def _profile_dir(name: str) -> Path | None:
    """Directory holding a profile, or None for a name that can't be stored.

    Names are sanitized for the filesystem, so different names can sanitize to
    the same folder ("a b" / "a_b"); the later one gets a hash suffix instead of
    silently overwriting the first.
    """
    if not name.strip():
        return None
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    base = PROFILES_DIR / safe
    try:
        with open(base / "profile.json") as f:
            stored = json.load(f).get("name")
    except (OSError, ValueError, AttributeError):
        stored = None
    if stored is None or stored == name:
        return base
    digest = hashlib.sha1(name.encode()).hexdigest()[:8]
    return PROFILES_DIR / f"{safe}-{digest}"


def ensure_profiles_dir() -> Path:
    """Create profiles directory if needed."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return PROFILES_DIR


def list_profiles() -> list[Profile]:
    """List all saved profiles."""
    ensure_profiles_dir()
    profiles = []

    for p in sorted(PROFILES_DIR.iterdir()):
        if p.is_dir():
            meta_path = p / "profile.json"
            if meta_path.is_file():
                try:
                    with open(meta_path) as f:
                        data = json.load(f)
                    profiles.append(Profile(
                        name=data.get("name", p.name),
                        description=data.get("description", ""),
                        created_at=data.get("created_at", 0),
                        updated_at=data.get("updated_at", 0),
                        entries=data.get("entries", {}),
                    ))
                except (json.JSONDecodeError, OSError):
                    continue
    return profiles


def save_profile(name: str, description: str,
                 dotfile_entries: list) -> Profile:
    """Save current dotfile state as a profile.

    Args:
        name: Profile name
        description: Profile description
        dotfile_entries: List of DotfileEntry objects
    """
    ensure_profiles_dir()

    profile_dir = _profile_dir(name)
    if profile_dir is None:
        raise ValueError("Profile name cannot be empty")
    profile_dir.mkdir(parents=True, exist_ok=True)
    configs_dir = profile_dir / "configs"
    shutil.rmtree(configs_dir, ignore_errors=True)  # drop snapshots of removed entries
    configs_dir.mkdir()

    now = time.time()
    entries = {}

    for entry in dotfile_entries:
        config_path = entry.get_config_path()
        snapshot_name = None

        if config_path and os.path.isfile(config_path):
            snapshot_name = entry.name + "__" + os.path.basename(config_path)
            shutil.copy2(config_path, configs_dir / snapshot_name)

        entries[entry.name] = {
            "enabled": entry.enabled,
            "display_name": entry.display_name,
            "config_snapshot": snapshot_name,
            "original_path": config_path or "",
        }

    profile = Profile(
        name=name,
        description=description,
        created_at=now,
        updated_at=now,
        entries=entries,
    )

    meta = {
        "name": name,
        "description": description,
        "created_at": now,
        "updated_at": now,
        "entries": entries,
    }

    with open(profile_dir / "profile.json", "w") as f:
        json.dump(meta, f, indent=2)

    return profile


def load_profile(profile_name: str, dotfile_entries: list) -> list[str]:
    """Load a profile, restoring enabled states and optionally configs.

    Returns list of actions taken.
    """
    profile_dir = _profile_dir(profile_name)
    if profile_dir is None or not (profile_dir / "profile.json").is_file():
        return [f"Profile '{profile_name}' not found"]
    meta_path = profile_dir / "profile.json"

    try:
        with open(meta_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ["Failed to read profile"]

    entries_data = data.get("entries", {})
    configs_dir = profile_dir / "configs"
    actions = []

    entry_map = {e.name: e for e in dotfile_entries}

    for name, info in entries_data.items():
        entry = entry_map.get(name)
        if entry is None:
            actions.append(f"Skipped {name} (not found on system)")
            continue

        # Restore enabled state
        old_enabled = entry.enabled
        entry.enabled = info.get("enabled", True)
        if old_enabled != entry.enabled:
            state = "enabled" if entry.enabled else "disabled"
            actions.append(f"{entry.display_name}: {state}")

        # Restore config snapshot
        snapshot = info.get("config_snapshot")
        if snapshot and configs_dir.is_dir():
            snapshot_path = configs_dir / snapshot
            target = info.get("original_path", "")
            if snapshot_path.is_file() and target and os.path.isfile(target):
                # Backup current
                from dfm.core.backup import create_backup
                create_backup(target, reason=f"profile-load:{profile_name}")
                shutil.copy2(snapshot_path, target)
                actions.append(f"{entry.display_name}: config restored")

    return actions


def delete_profile(profile_name: str) -> bool:
    """Delete a profile."""
    profile_dir = _profile_dir(profile_name)
    if profile_dir is None or profile_dir == PROFILES_DIR:
        return False

    if (profile_dir / "profile.json").is_file():
        shutil.rmtree(profile_dir)
        return True
    return False


def export_profile_json(profile_name: str) -> str | None:
    """Export a profile as a JSON string for sharing."""
    profile_dir = _profile_dir(profile_name)
    if profile_dir is None or not (profile_dir / "profile.json").is_file():
        return None
    meta_path = profile_dir / "profile.json"

    try:
        with open(meta_path) as f:
            data = json.load(f)

        # Include config contents inline for sharing
        configs_dir = profile_dir / "configs"
        if configs_dir.is_dir():
            config_contents = {}
            for entry_name, info in data.get("entries", {}).items():
                snapshot = info.get("config_snapshot")
                if snapshot:
                    snapshot_path = configs_dir / snapshot
                    if snapshot_path.is_file():
                        try:
                            config_contents[entry_name] = snapshot_path.read_text(errors="replace")
                        except OSError:
                            pass
            data["config_contents"] = config_contents

        return json.dumps(data, indent=2)
    except (json.JSONDecodeError, OSError):
        return None
