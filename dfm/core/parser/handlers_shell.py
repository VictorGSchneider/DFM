"""Parsers for shell configs (.bashrc/.zshrc) and i3-like window manager configs."""

import os
import re

from dfm.core.parser.types import ConfigField, FieldType
from dfm.core.parser.infer import make_display_name


def parse_shell(content: str) -> list[ConfigField]:
    """Parse shell config files (.bashrc, .zshrc, etc.)."""
    fields = []
    current_section = "General"
    comment_buffer = ""

    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()

        if not stripped:
            comment_buffer = ""
            continue

        if stripped.startswith("#"):
            current_section, comment_buffer, header = _shell_comment(
                stripped, current_section, line, line_num,
            )
            if header is not None:
                fields.append(header)
            continue

        field_obj = _parse_shell_statement(stripped, line, line_num,
                                           current_section, comment_buffer)
        if field_obj is not None:
            fields.append(field_obj)
            comment_buffer = ""

    return fields


def _shell_comment(stripped: str, current_section: str, line: str,
                   line_num: int) -> tuple[str, str, ConfigField | None]:
    """Handle a shell comment line; return (section, buffer, optional header)."""
    inner = stripped.lstrip("# ").strip()
    if (inner.startswith("===") or inner.startswith("---") or
            inner.startswith("***") or inner.isupper()):
        section_name = inner.strip("=-*# ").strip()
        if section_name:
            header = ConfigField(
                key=section_name,
                display_name=section_name.title(),
                value="",
                field_type=FieldType.COMMENT,
                section=section_name.title(),
                line_number=line_num,
                original_line=line,
            )
            return section_name.title(), "", header
    return current_section, inner, None


def _parse_shell_statement(stripped: str, line: str, line_num: int,
                           section: str, comment: str) -> ConfigField | None:
    """Match a single shell statement and return a ConfigField if recognized."""
    match = re.match(r"^export\s+([\w]+)=(.*)", stripped)
    if match:
        key, value = match.group(1), match.group(2).strip().strip("\"'")
        return ConfigField(
            key=key, display_name=make_display_name(key), value=value,
            field_type=FieldType.TEXT, section=section, comment=comment,
            line_number=line_num, original_line=line,
        )

    match = re.match(r"^([\w]+)=(.*)", stripped)
    if match and not stripped.startswith("if") and not stripped.startswith("for"):
        key, value = match.group(1), match.group(2).strip().strip("\"'")
        return ConfigField(
            key=key, display_name=make_display_name(key), value=value,
            field_type=FieldType.TEXT, section=section, comment=comment,
            line_number=line_num, original_line=line,
        )

    match = re.match(r"^alias\s+([\w\-]+)=['\"]?(.*?)['\"]?$", stripped)
    if match:
        key, value = match.group(1), match.group(2)
        return ConfigField(
            key=f"alias:{key}", display_name=f"Alias: {key}", value=value,
            field_type=FieldType.TEXT, section="Aliases", comment=comment,
            line_number=line_num, original_line=line,
        )

    match = re.match(r"^(setopt|unsetopt)\s+([\w]+)", stripped)
    if match:
        cmd, opt = match.group(1), match.group(2)
        return ConfigField(
            key=opt, display_name=make_display_name(opt),
            value="true" if cmd == "setopt" else "false",
            field_type=FieldType.TOGGLE, section="Shell Options",
            comment=comment, line_number=line_num, original_line=line,
        )

    match = re.match(r"^set\s+([+-])o\s+([\w]+)", stripped)
    if match:
        sign, opt = match.group(1), match.group(2)
        return ConfigField(
            key=opt, display_name=make_display_name(opt),
            value="true" if sign == "-" else "false",
            field_type=FieldType.TOGGLE, section="Shell Options",
            comment=comment, line_number=line_num, original_line=line,
        )

    match = re.match(r"^(?:source|\.)\s+(.*)", stripped)
    if match:
        path = match.group(1).strip().strip("\"'")
        return ConfigField(
            key=f"source:{os.path.basename(path)}",
            display_name=f"Source: {os.path.basename(path)}",
            value=path, field_type=FieldType.PATH, section="Sources",
            comment=comment, line_number=line_num, original_line=line,
        )

    return None


def parse_i3_like(content: str) -> list[ConfigField]:
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
                    inner.isupper() or (len(inner) < 40 and " = " not in inner)):
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
                    comment_buffer = ""
                    continue
            comment_buffer = inner
            continue

        field_obj = _parse_i3_statement(stripped, line, line_num,
                                        current_section, comment_buffer)
        if field_obj is not None:
            fields.append(field_obj)
            comment_buffer = ""

    return fields


def _parse_i3_statement(stripped: str, line: str, line_num: int,
                       current_section: str, comment: str) -> ConfigField | None:
    """Match a single i3 statement and return a ConfigField if recognized."""
    match = re.match(r"^set\s+\$(\w+)\s+(.*)", stripped)
    if match:
        key, value = match.group(1), match.group(2).strip()
        return ConfigField(
            key=key, display_name=make_display_name(key), value=value,
            field_type=FieldType.TEXT, section="Variables", comment=comment,
            line_number=line_num, original_line=line,
        )

    match = re.match(r"^(bindsym|bindcode)\s+(.*)", stripped)
    if match:
        value = match.group(2).strip()
        parts = value.split(None, 1)
        if len(parts) == 2:
            key_combo, action = parts
        else:
            key_combo, action = value, ""
        return ConfigField(
            key=f"bind:{key_combo}", display_name=key_combo, value=action,
            field_type=FieldType.KEYBIND, section="Key Bindings",
            comment=comment, line_number=line_num, original_line=line,
        )

    match = re.match(r"^([\w_-]+)\s+(.*)", stripped)
    if match:
        key, value = match.group(1), match.group(2).strip()
        if key in ("exec", "exec_always"):
            section = "Autostart"
        elif key in ("for_window",):
            section = "Window Rules"
        else:
            section = current_section
        return ConfigField(
            key=key, display_name=make_display_name(key), value=value,
            field_type=FieldType.TEXT, section=section, comment=comment,
            line_number=line_num, original_line=line,
        )

    return None
