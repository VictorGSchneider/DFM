"""Config file parser - analyzes dotfiles and generates appropriate UI fields."""

import os
import re
import json
from dataclasses import dataclass, field
from enum import Enum, auto


class FieldType(Enum):
    """Types of UI fields that can be generated."""
    TOGGLE = auto()       # Boolean on/off
    TEXT = auto()          # Single-line text input
    MULTILINE = auto()    # Multi-line text
    NUMBER = auto()       # Numeric input
    SLIDER = auto()       # Numeric range with slider
    DROPDOWN = auto()     # Selection from known values
    COLOR = auto()        # Color picker
    KEYBIND = auto()      # Keyboard shortcut
    PATH = auto()         # File/directory path
    FONT = auto()         # Font selection
    COMMENT = auto()      # Section header / comment group
    RAW = auto()          # Raw text (unparsed lines)


@dataclass
class ConfigField:
    """A single configuration field parsed from a dotfile."""
    key: str
    display_name: str
    value: str
    field_type: FieldType
    section: str = ""
    comment: str = ""
    line_number: int = 0
    options: list[str] = field(default_factory=list)
    min_val: float = 0
    max_val: float = 100
    step: float = 1
    original_line: str = ""
    is_commented_out: bool = False


@dataclass
class ParsedConfig:
    """Result of parsing a config file."""
    fields: list[ConfigField]
    file_path: str
    file_format: str  # ini, toml, shell, xresources, i3, json, yaml, unknown
    raw_content: str = ""
    sections: list[str] = field(default_factory=list)


# Patterns for detecting value types
BOOL_TRUE = {"true", "yes", "on", "1", "enabled", "enable"}
BOOL_FALSE = {"false", "no", "off", "0", "disabled", "disable"}
COLOR_PATTERN = re.compile(r"^#([0-9a-fA-F]{3,8})$|^rgb[a]?\(.*\)$")
PATH_PATTERN = re.compile(r"^[~/][\w/.~\-]+$")
FONT_PATTERN = re.compile(r"^[\w\s]+ \d+(\.\d+)?$|font|typeface", re.IGNORECASE)
KEYBIND_KEYWORDS = {"bindsym", "bind", "keybind", "shortcut", "hotkey",
                    "key", "mod", "super", "ctrl", "alt", "shift"}
SLIDER_KEYS = {"opacity", "alpha", "transparency", "volume", "brightness",
               "gap", "gaps", "border", "radius", "margin", "padding",
               "size", "width", "height", "speed", "rate", "delay",
               "timeout", "interval", "columns", "rows", "scale",
               "blur", "rounding", "shadow", "dim", "inactive_opacity",
               "active_opacity", "fullscreen_opacity"}


def parse_config(filepath: str) -> ParsedConfig:
    """Parse a config file and return structured fields."""
    try:
        with open(filepath, "r", errors="replace") as f:
            content = f.read()
    except (PermissionError, FileNotFoundError):
        return ParsedConfig(fields=[], file_path=filepath, file_format="unknown")

    file_format = _detect_format(filepath, content)

    if file_format == "json":
        fields = _parse_json(content)
    elif file_format == "ini":
        fields = _parse_ini(content)
    elif file_format == "toml":
        fields = _parse_toml(content)
    elif file_format == "xresources":
        fields = _parse_xresources(content)
    elif file_format == "i3":
        fields = _parse_i3_like(content)
    elif file_format == "shell":
        fields = _parse_shell(content)
    else:
        fields = _parse_generic(content)

    # Assign line numbers and detect field types
    for i, f in enumerate(fields):
        f.line_number = f.line_number or i + 1
        if f.field_type == FieldType.TEXT:
            f.field_type = _infer_field_type(f.key, f.value)

    sections = list(dict.fromkeys(f.section for f in fields if f.section))

    return ParsedConfig(
        fields=fields,
        file_path=filepath,
        file_format=file_format,
        raw_content=content,
        sections=sections,
    )


def _detect_format(filepath: str, content: str) -> str:
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

    # Content-based detection
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


def _infer_field_type(key: str, value: str) -> FieldType:
    """Infer the best UI field type from a key-value pair."""
    val_lower = value.lower().strip()
    key_lower = key.lower().replace("-", "_").replace(".", "_")

    # Boolean
    if val_lower in BOOL_TRUE or val_lower in BOOL_FALSE:
        return FieldType.TOGGLE

    # Color
    if COLOR_PATTERN.match(value.strip()):
        return FieldType.COLOR
    if "color" in key_lower or "colour" in key_lower:
        if COLOR_PATTERN.match(value.strip()):
            return FieldType.COLOR

    # Numeric / Slider
    try:
        float(value.strip())
        key_parts = set(key_lower.replace("_", " ").replace("-", " ").split())
        if key_parts & SLIDER_KEYS or any(s in key_lower for s in SLIDER_KEYS):
            return FieldType.SLIDER
        return FieldType.NUMBER
    except ValueError:
        pass

    # Path
    if PATH_PATTERN.match(value.strip()) or "path" in key_lower or "dir" in key_lower:
        stripped = value.strip()
        if stripped.startswith(("/", "~", "$HOME")):
            return FieldType.PATH

    # Font
    if "font" in key_lower:
        return FieldType.FONT

    # Keybind
    key_parts_set = set(key_lower.replace("_", " ").replace("-", " ").split())
    if key_parts_set & KEYBIND_KEYWORDS:
        return FieldType.KEYBIND

    return FieldType.TEXT


def _make_display_name(key: str) -> str:
    """Convert a config key into a human-readable display name."""
    name = key
    # Remove common prefixes
    for prefix in ("set ", "set-", "setopt ", "unsetopt "):
        if name.lower().startswith(prefix):
            name = name[len(prefix):]
            break

    # Replace separators with spaces
    name = name.replace("_", " ").replace("-", " ").replace(".", " > ")

    # Title case
    name = name.strip().title()

    return name


def _parse_ini(content: str) -> list[ConfigField]:
    """Parse INI-style config files."""
    fields = []
    current_section = ""
    comment_buffer = ""

    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()

        if not stripped:
            comment_buffer = ""
            continue

        if stripped.startswith(("#", ";")):
            comment_buffer = stripped.lstrip("#; ").strip()
            continue

        # Section header
        match = re.match(r"^\[(.+)\]$", stripped)
        if match:
            current_section = match.group(1).strip()
            fields.append(ConfigField(
                key=current_section,
                display_name=current_section,
                value="",
                field_type=FieldType.COMMENT,
                section=current_section,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""
            continue

        # Key=Value
        match = re.match(r"^([\w.\-]+)\s*=\s*(.*)", stripped)
        if match:
            key, value = match.group(1), match.group(2).strip()
            fields.append(ConfigField(
                key=key,
                display_name=_make_display_name(key),
                value=value,
                field_type=FieldType.TEXT,
                section=current_section,
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""

    return fields


def _parse_toml(content: str) -> list[ConfigField]:
    """Parse TOML-style config (simplified)."""
    # Reuse INI parser as TOML is a superset for basic cases
    return _parse_ini(content)


def _parse_shell(content: str) -> list[ConfigField]:
    """Parse shell config files (.bashrc, .zshrc, etc.)."""
    fields = []
    current_section = "General"
    comment_buffer = ""

    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()

        if not stripped:
            comment_buffer = ""
            continue

        # Detect section-like comments (e.g., "# === Aliases ===")
        if stripped.startswith("#"):
            inner = stripped.lstrip("# ").strip()
            if (inner.startswith("===") or inner.startswith("---") or
                    inner.startswith("***") or inner.isupper()):
                section_name = inner.strip("=-*# ").strip()
                if section_name:
                    current_section = section_name.title()
                    fields.append(ConfigField(
                        key=section_name,
                        display_name=section_name.title(),
                        value="",
                        field_type=FieldType.COMMENT,
                        section=current_section,
                        line_number=line_num,
                        original_line=line,
                    ))
                    comment_buffer = ""
                    continue
            comment_buffer = inner
            continue

        # export VAR=value
        match = re.match(r"^export\s+([\w]+)=(.*)", stripped)
        if match:
            key, value = match.group(1), match.group(2).strip().strip("\"'")
            fields.append(ConfigField(
                key=key,
                display_name=_make_display_name(key),
                value=value,
                field_type=FieldType.TEXT,
                section=current_section,
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""
            continue

        # VAR=value (without export)
        match = re.match(r"^([\w]+)=(.*)", stripped)
        if match and not stripped.startswith("if") and not stripped.startswith("for"):
            key, value = match.group(1), match.group(2).strip().strip("\"'")
            fields.append(ConfigField(
                key=key,
                display_name=_make_display_name(key),
                value=value,
                field_type=FieldType.TEXT,
                section=current_section,
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""
            continue

        # alias name='command'
        match = re.match(r"^alias\s+([\w\-]+)=['\"]?(.*?)['\"]?$", stripped)
        if match:
            key, value = match.group(1), match.group(2)
            fields.append(ConfigField(
                key=f"alias:{key}",
                display_name=f"Alias: {key}",
                value=value,
                field_type=FieldType.TEXT,
                section="Aliases",
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""
            continue

        # setopt / unsetopt (zsh)
        match = re.match(r"^(setopt|unsetopt)\s+([\w]+)", stripped)
        if match:
            cmd, opt = match.group(1), match.group(2)
            fields.append(ConfigField(
                key=opt,
                display_name=_make_display_name(opt),
                value="true" if cmd == "setopt" else "false",
                field_type=FieldType.TOGGLE,
                section="Shell Options",
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""
            continue

        # set -o / set +o (bash)
        match = re.match(r"^set\s+([+-])o\s+([\w]+)", stripped)
        if match:
            sign, opt = match.group(1), match.group(2)
            fields.append(ConfigField(
                key=opt,
                display_name=_make_display_name(opt),
                value="true" if sign == "-" else "false",
                field_type=FieldType.TOGGLE,
                section="Shell Options",
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""
            continue

        # source / . commands
        match = re.match(r"^(?:source|\.)\s+(.*)", stripped)
        if match:
            path = match.group(1).strip().strip("\"'")
            fields.append(ConfigField(
                key=f"source:{os.path.basename(path)}",
                display_name=f"Source: {os.path.basename(path)}",
                value=path,
                field_type=FieldType.PATH,
                section="Sources",
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""
            continue

    return fields


def _parse_xresources(content: str) -> list[ConfigField]:
    """Parse X Resources files."""
    fields = []
    comment_buffer = ""

    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()

        if not stripped:
            comment_buffer = ""
            continue

        if stripped.startswith("!") or stripped.startswith("#"):
            comment_buffer = stripped.lstrip("!# ").strip()
            continue

        # resource: value
        match = re.match(r"^([*\w.]+)\s*:\s*(.*)", stripped)
        if match:
            key, value = match.group(1), match.group(2).strip()
            section = key.split(".")[0] if "." in key else "General"
            fields.append(ConfigField(
                key=key,
                display_name=_make_display_name(key.split(".")[-1]),
                value=value,
                field_type=FieldType.TEXT,
                section=section,
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""

    return fields


def _parse_i3_like(content: str) -> list[ConfigField]:
    """Parse i3/sway/hyprland-like config files."""
    fields = []
    current_section = "General"
    comment_buffer = ""

    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()

        if not stripped:
            comment_buffer = ""
            continue

        if stripped.startswith("#"):
            inner = stripped.lstrip("# ").strip()
            if (inner.startswith("===") or inner.startswith("---") or
                    inner.isupper() or (len(inner) < 40 and not " = " in inner)):
                section_name = inner.strip("=-*# ").strip()
                if section_name and len(section_name) > 2:
                    current_section = section_name.title()
                    fields.append(ConfigField(
                        key=section_name,
                        display_name=section_name.title(),
                        value="",
                        field_type=FieldType.COMMENT,
                        section=current_section,
                        line_number=line_num,
                        original_line=line,
                    ))
            comment_buffer = inner
            continue

        # set $var value
        match = re.match(r"^set\s+\$(\w+)\s+(.*)", stripped)
        if match:
            key, value = match.group(1), match.group(2).strip()
            fields.append(ConfigField(
                key=key,
                display_name=_make_display_name(key),
                value=value,
                field_type=FieldType.TEXT,
                section="Variables",
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""
            continue

        # bindsym/bindcode
        match = re.match(r"^(bindsym|bindcode)\s+(.*)", stripped)
        if match:
            value = match.group(2).strip()
            parts = value.split(None, 1)
            if len(parts) == 2:
                key_combo, action = parts
            else:
                key_combo, action = value, ""
            fields.append(ConfigField(
                key=f"bind:{key_combo}",
                display_name=key_combo,
                value=action,
                field_type=FieldType.KEYBIND,
                section="Key Bindings",
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""
            continue

        # key value pairs (e.g., "gaps inner 10")
        match = re.match(r"^([\w_-]+)\s+(.*)", stripped)
        if match:
            key, value = match.group(1), match.group(2).strip()
            if key in ("exec", "exec_always"):
                section = "Autostart"
                ftype = FieldType.TEXT
            elif key in ("for_window",):
                section = "Window Rules"
                ftype = FieldType.TEXT
            else:
                section = current_section
                ftype = FieldType.TEXT
            fields.append(ConfigField(
                key=key,
                display_name=_make_display_name(key),
                value=value,
                field_type=ftype,
                section=section,
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""

    return fields


def _parse_json(content: str) -> list[ConfigField]:
    """Parse JSON config files."""
    fields = []
    try:
        data = json.loads(content)
        _flatten_json(data, fields, "")
    except json.JSONDecodeError:
        return _parse_generic(content)
    return fields


def _flatten_json(data: dict | list, fields: list[ConfigField], prefix: str,
                  section: str = "General") -> None:
    """Flatten a JSON structure into config fields."""
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                fields.append(ConfigField(
                    key=full_key,
                    display_name=_make_display_name(key),
                    value="",
                    field_type=FieldType.COMMENT,
                    section=key.title(),
                ))
                _flatten_json(value, fields, full_key, key.title())
            elif isinstance(value, list):
                fields.append(ConfigField(
                    key=full_key,
                    display_name=_make_display_name(key),
                    value=json.dumps(value),
                    field_type=FieldType.MULTILINE,
                    section=section,
                ))
            elif isinstance(value, bool):
                fields.append(ConfigField(
                    key=full_key,
                    display_name=_make_display_name(key),
                    value=str(value).lower(),
                    field_type=FieldType.TOGGLE,
                    section=section,
                ))
            elif isinstance(value, (int, float)):
                fields.append(ConfigField(
                    key=full_key,
                    display_name=_make_display_name(key),
                    value=str(value),
                    field_type=FieldType.TEXT,
                    section=section,
                ))
            else:
                fields.append(ConfigField(
                    key=full_key,
                    display_name=_make_display_name(key),
                    value=str(value),
                    field_type=FieldType.TEXT,
                    section=section,
                ))


def _parse_generic(content: str) -> list[ConfigField]:
    """Parse any config file with generic key=value or key: value detection."""
    fields = []
    current_section = "General"
    comment_buffer = ""

    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()

        if not stripped:
            comment_buffer = ""
            continue

        if stripped.startswith(("#", ";", "//", "!")):
            comment_buffer = stripped.lstrip("#;/! ").strip()
            continue

        # Section headers [section]
        match = re.match(r"^\[(.+)\]$", stripped)
        if match:
            current_section = match.group(1).strip()
            fields.append(ConfigField(
                key=current_section,
                display_name=current_section,
                value="",
                field_type=FieldType.COMMENT,
                section=current_section,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""
            continue

        # key = value
        match = re.match(r"^([\w.\-]+)\s*[=:]\s*(.*)", stripped)
        if match:
            key, value = match.group(1), match.group(2).strip().strip("\"'")
            fields.append(ConfigField(
                key=key,
                display_name=_make_display_name(key),
                value=value,
                field_type=FieldType.TEXT,
                section=current_section,
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""
            continue

        # key value (space separated, like i3 configs)
        match = re.match(r"^([\w_-]+)\s+(.*)", stripped)
        if match:
            key, value = match.group(1), match.group(2).strip()
            fields.append(ConfigField(
                key=key,
                display_name=_make_display_name(key),
                value=value,
                field_type=FieldType.TEXT,
                section=current_section,
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""

    return fields


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

    # Reconstruct the line with the new value
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

    # INI / generic key=value
    match = re.match(r"^([\w.\-]+\s*=\s*)(.*)$", stripped)
    if match:
        prefix = match.group(1)
        indent = old_line[:len(old_line) - len(old_line.lstrip())]
        return f"{indent}{prefix}{new_value}\n"

    # key: value
    match = re.match(r"^([\w.\-]+\s*:\s*)(.*)$", stripped)
    if match:
        prefix = match.group(1)
        indent = old_line[:len(old_line) - len(old_line.lstrip())]
        return f"{indent}{prefix}{new_value}\n"

    # export VAR=value
    match = re.match(r"^(export\s+[\w]+=)(.*)$", stripped)
    if match:
        prefix = match.group(1)
        indent = old_line[:len(old_line) - len(old_line.lstrip())]
        return f'{indent}{prefix}"{new_value}"\n'

    # set $var value
    match = re.match(r"^(set\s+\$\w+\s+)(.*)$", stripped)
    if match:
        prefix = match.group(1)
        indent = old_line[:len(old_line) - len(old_line.lstrip())]
        return f"{indent}{prefix}{new_value}\n"

    # setopt/unsetopt
    match = re.match(r"^(setopt|unsetopt)\s+([\w]+)", stripped)
    if match:
        opt = match.group(2)
        indent = old_line[:len(old_line) - len(old_line.lstrip())]
        if new_value.lower() in BOOL_TRUE:
            return f"{indent}setopt {opt}\n"
        else:
            return f"{indent}unsetopt {opt}\n"

    # Generic space-separated (key value)
    match = re.match(r"^([\w_-]+\s+)(.*)$", stripped)
    if match:
        prefix = match.group(1)
        indent = old_line[:len(old_line) - len(old_line.lstrip())]
        return f"{indent}{prefix}{new_value}\n"

    return None
