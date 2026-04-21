"""Update individual config values on disk while preserving formatting."""

import re

from dfm.core.parser.types import ConfigField, BOOL_TRUE


def update_config_value(filepath: str, field: ConfigField, new_value: str) -> bool:
    """Update a single value in a config file."""
    try:
        with open(filepath, "r", errors="replace") as f:
            lines = f.readlines()
    except (PermissionError, FileNotFoundError):
        return False

    if field.line_number < 1 or field.line_number > len(lines):
        return False

    idx = field.line_number - 1
    old_line = lines[idx]

    new_line = _rebuild_line(old_line, field, new_value)
    if new_line is None:
        return False

    lines[idx] = new_line

    try:
        with open(filepath, "w") as f:
            f.writelines(lines)
        return True
    except PermissionError:
        return False


def _rebuild_line(old_line: str, field: ConfigField, new_value: str) -> str | None:
    """Rebuild a config line with a new value, preserving formatting."""
    stripped = old_line.strip()
    indent = old_line[:len(old_line) - len(old_line.lstrip())]

    match = re.match(r"^([\w.\-]+\s*=\s*)(.*)$", stripped)
    if match:
        return f"{indent}{match.group(1)}{new_value}\n"

    match = re.match(r"^([\w.\-]+\s*:\s*)(.*)$", stripped)
    if match:
        return f"{indent}{match.group(1)}{new_value}\n"

    match = re.match(r"^(export\s+[\w]+=)(.*)$", stripped)
    if match:
        return f'{indent}{match.group(1)}"{new_value}"\n'

    match = re.match(r"^(set\s+\$\w+\s+)(.*)$", stripped)
    if match:
        return f"{indent}{match.group(1)}{new_value}\n"

    match = re.match(r"^(setopt|unsetopt)\s+([\w]+)", stripped)
    if match:
        opt = match.group(2)
        if new_value.lower() in BOOL_TRUE:
            return f"{indent}setopt {opt}\n"
        return f"{indent}unsetopt {opt}\n"

    match = re.match(r"^([\w_-]+\s+)(.*)$", stripped)
    if match:
        return f"{indent}{match.group(1)}{new_value}\n"

    return None
