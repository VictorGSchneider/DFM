"""Parsers for INI, XResources, and generic key=value files."""

import re

from dfm.core.parser.types import ConfigField, FieldType
from dfm.core.parser.infer import make_display_name


def parse_ini(content: str) -> list[ConfigField]:
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

        match = re.match(r"^([\w.\-]+)\s*=\s*(.*)", stripped)
        if match:
            key, value = match.group(1), match.group(2).strip()
            fields.append(ConfigField(
                key=key,
                display_name=make_display_name(key),
                value=value,
                field_type=FieldType.TEXT,
                section=current_section,
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""

    return fields


def parse_xresources(content: str) -> list[ConfigField]:
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

        match = re.match(r"^([*\w.]+)\s*:\s*(.*)", stripped)
        if match:
            key, value = match.group(1), match.group(2).strip()
            section = key.split(".")[0] if "." in key else "General"
            fields.append(ConfigField(
                key=key,
                display_name=make_display_name(key.split(".")[-1]),
                value=value,
                field_type=FieldType.TEXT,
                section=section,
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""

    return fields


def parse_generic(content: str) -> list[ConfigField]:
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

        match = re.match(r"^([\w.\-]+)\s*[=:]\s*(.*)", stripped)
        if match:
            key, value = match.group(1), match.group(2).strip().strip("\"'")
            fields.append(ConfigField(
                key=key,
                display_name=make_display_name(key),
                value=value,
                field_type=FieldType.TEXT,
                section=current_section,
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""
            continue

        match = re.match(r"^([\w_-]+)\s+(.*)", stripped)
        if match:
            key, value = match.group(1), match.group(2).strip()
            fields.append(ConfigField(
                key=key,
                display_name=make_display_name(key),
                value=value,
                field_type=FieldType.TEXT,
                section=current_section,
                comment=comment_buffer,
                line_number=line_num,
                original_line=line,
            ))
            comment_buffer = ""

    return fields
