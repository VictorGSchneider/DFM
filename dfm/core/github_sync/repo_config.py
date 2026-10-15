"""Persistent config for the user's dotfiles repo path."""

import json
import os
import tempfile
from pathlib import Path


def _config_file() -> str:
    return os.path.join(str(Path.home()), ".config", "dfm", "config.json")


def _load() -> dict:
    """Read the config; anything unreadable or not a JSON object counts as empty."""
    try:
        with open(_config_file(), encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):  # ValueError covers bad JSON and bad UTF-8
        return {}
    return cfg if isinstance(cfg, dict) else {}


def get_repo_path() -> str:
    """Get the local dotfiles repo path."""
    path = _load().get("repo_path", "")
    return path if isinstance(path, str) else ""


def save_repo_path(path: str) -> None:
    """Save the configured repo path."""
    config_file = _config_file()
    os.makedirs(os.path.dirname(config_file), exist_ok=True)

    cfg = _load()
    cfg["repo_path"] = path

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(config_file), prefix=".config-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, config_file)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
