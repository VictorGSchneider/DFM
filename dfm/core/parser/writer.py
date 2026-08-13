"""Update individual config values on disk while preserving formatting."""

import re

from dfm.core.parser.types import ConfigField, BOOL_TRUE, BOOL_FALSE
from dfm.core.parser.detect import detect_format
from dfm.core.parser.handlers_lua import ASSIGNMENT as LUA_ASSIGNMENT
from dfm.core.parser.handlers_lua import LONG_STRING, is_literal, split_lua_comment

_NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")


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

    if detect_format(filepath, "".join(lines)) == "lua":
        new_line = _rebuild_lua_line(old_line, new_value)
    else:
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


def _rebuild_lua_line(old_line: str, new_value: str) -> str | None:
    """Rebuild a Lua assignment, keeping quoting, commas and comments intact."""
    body = old_line.rstrip("\n")
    indent = body[:len(body) - len(body.lstrip())]

    code, comment = split_lua_comment(body.strip())
    gap = code[len(code.rstrip()):]
    code = code.rstrip()

    separator = ""
    while code.endswith((",", ";")):
        separator = code[-1] + separator
        code = code[:-1].rstrip()

    match = LUA_ASSIGNMENT.match(code)
    if match is None:
        # A keyless table item, e.g. `"waybar",` inside `exec-once = {`
        if not is_literal(code):
            return None
        return f"{indent}{_format_lua_value(code, new_value)}{separator}{gap}{comment}\n"

    prefix = code[:match.start("value")]
    value = _format_lua_value(match.group("value").strip(), new_value)

    return f"{indent}{prefix}{value}{separator}{gap}{comment}\n"


def _format_lua_value(old_value: str, new_value: str) -> str:
    """Render a new value the way the old one was written."""
    if len(old_value) >= 2 and old_value[0] == old_value[-1] and old_value[0] in "\"'":
        quote = old_value[0]
        escaped = new_value.replace("\\", "\\\\").replace(quote, f"\\{quote}")
        return f"{quote}{escaped}{quote}"

    match = LONG_STRING.match(old_value)
    if match:
        equals = match.group(1)
        return f"[{equals}[{new_value}]{equals}]"

    stripped = new_value.strip()
    lowered = stripped.lower()
    if lowered in ("nil",) or _NUMERIC.match(stripped):
        return stripped
    if lowered in BOOL_TRUE or lowered in BOOL_FALSE:
        return "true" if lowered in BOOL_TRUE else "false"

    # The old value was a bare expression (identifier, table, …) — keep it bare.
    return stripped
