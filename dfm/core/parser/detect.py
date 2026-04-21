"""Detect the format of a config file."""

import os
import re


def detect_format(filepath: str, content: str) -> str:
    """Detect the config file format."""
    basename = os.path.basename(filepath).lower()
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".json" or basename.endswith(".json"):
        return "json"
    if ext == ".toml" or basename.endswith(".toml"):
        return "toml"
    if ext in (".yaml", ".yml"):
        return "yaml"
    if ext in (".ini", ".cfg"):
        return "ini"

    if basename in (".xresources", ".xdefaults"):
        return "xresources"
    if basename in (".bashrc", ".zshrc", ".bash_profile", ".zprofile",
                    ".profile", ".aliases"):
        return "shell"
    if basename == "config" and ("bindsym" in content or "exec " in content):
        return "i3"

    content_start = content[:500]
    if content_start.lstrip().startswith("{"):
        return "json"
    if re.search(r"^\[[\w\s.:-]+\]", content_start, re.MULTILINE):
        if "=" in content_start:
            return "ini"
        return "toml"
    if re.search(r"^[\w.]+\s*:", content_start, re.MULTILINE) and "=" not in content_start:
        return "yaml"
    if re.search(r"^[\w.*]+:", content_start, re.MULTILINE) and "!" in content_start:
        return "xresources"
    if re.search(r"^(export |alias |if \[|source )", content_start, re.MULTILINE):
        return "shell"

    return "generic"
