"""Persistent config for the user's dotfiles repo path."""

import json
import os
from pathlib import Path


def _config_file() -> str:
    config_dir = os.path.join(str(Path.home()), ".config", "dfm")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "config.json")


def get_repo_path() -> str:
    """Get the local dotfiles repo path."""
    config_file = _config_file()
    if os.path.isfile(config_file):
        try:
            with open(config_file) as f:
                cfg = json.load(f)
            return cfg.get("repo_path", "")
        except (json.JSONDecodeError, PermissionError):
            pass
    return ""


def save_repo_path(path: str) -> None:
    """Save the configured repo path."""
    config_file = _config_file()

    cfg: dict = {}
    if os.path.isfile(config_file):
        try:
            with open(config_file) as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, PermissionError):
            pass

    cfg["repo_path"] = path
    with open(config_file, "w") as f:
        json.dump(cfg, f, indent=2)
