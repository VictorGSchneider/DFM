"""Config file parser - analyzes dotfiles and generates appropriate UI fields."""

from dfm.core.parser.types import (
    FieldType,
    ConfigField,
    ParsedConfig,
    BOOL_TRUE,
    BOOL_FALSE,
)
from dfm.core.parser.detect import detect_format as _detect_format
from dfm.core.parser.infer import infer_field_type, make_display_name
from dfm.core.parser.handlers import (
    parse_ini,
    parse_toml,
    parse_yaml,
    parse_shell,
    parse_xresources,
    parse_i3_like,
    parse_json,
    parse_generic,
)
from dfm.core.parser.writer import update_config_value


def parse_config(filepath: str) -> ParsedConfig:
    """Parse a config file and return structured fields."""
    try:
        with open(filepath, "r", errors="replace") as f:
            content = f.read()
    except (PermissionError, FileNotFoundError):
        return ParsedConfig(fields=[], file_path=filepath, file_format="unknown")

    file_format = _detect_format(filepath, content)

    handlers = {
        "json": parse_json,
        "ini": parse_ini,
        "toml": parse_toml,
        "yaml": parse_yaml,
        "xresources": parse_xresources,
        "i3": parse_i3_like,
        "shell": parse_shell,
    }
    fields = handlers.get(file_format, parse_generic)(content)

    for i, f in enumerate(fields):
        f.line_number = f.line_number or i + 1
        if f.field_type == FieldType.TEXT:
            f.field_type = infer_field_type(f.key, f.value)

    sections = list(dict.fromkeys(f.section for f in fields if f.section))

    return ParsedConfig(
        fields=fields,
        file_path=filepath,
        file_format=file_format,
        raw_content=content,
        sections=sections,
    )


__all__ = [
    "FieldType",
    "ConfigField",
    "ParsedConfig",
    "BOOL_TRUE",
    "BOOL_FALSE",
    "parse_config",
    "update_config_value",
]
