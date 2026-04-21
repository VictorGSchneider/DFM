"""Parsers for structured formats (TOML, YAML, JSON)."""

import json

from dfm.core.parser.types import ConfigField, FieldType
from dfm.core.parser.infer import make_display_name
from dfm.core.parser.handlers_basic import parse_ini, parse_generic


def parse_toml(content: str) -> list[ConfigField]:
    """Parse TOML config files using tomllib/tomli when available."""
    try:
        import tomllib
        return _structured_to_fields(tomllib.loads(content))
    except ImportError:
        pass
    try:
        import tomli
        return _structured_to_fields(tomli.loads(content))
    except ImportError:
        pass
    return parse_ini(content)


def parse_yaml(content: str) -> list[ConfigField]:
    """Parse YAML config files using PyYAML when available."""
    try:
        import yaml
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            return _structured_to_fields(data)
        elif isinstance(data, list):
            return _structured_to_fields({"items": data})
    except ImportError:
        pass
    except Exception:
        pass
    return parse_generic(content)


def parse_json(content: str) -> list[ConfigField]:
    """Parse JSON config files."""
    fields: list[ConfigField] = []
    try:
        data = json.loads(content)
        _flatten_json(data, fields, "")
    except json.JSONDecodeError:
        return parse_generic(content)
    return fields


def _structured_to_fields(data: dict, prefix: str = "",
                          section: str = "General") -> list[ConfigField]:
    """Convert a parsed TOML/YAML dict into a ConfigField list."""
    fields: list[ConfigField] = []
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else str(key)
        display = make_display_name(str(key))
        if isinstance(value, dict):
            fields.append(ConfigField(
                key=full_key, display_name=display, value="",
                field_type=FieldType.COMMENT, section=str(key).title(),
            ))
            fields.extend(_structured_to_fields(value, full_key, str(key).title()))
        elif isinstance(value, list):
            fields.append(ConfigField(
                key=full_key, display_name=display,
                value=json.dumps(value),
                field_type=FieldType.MULTILINE, section=section,
            ))
        elif isinstance(value, bool):
            fields.append(ConfigField(
                key=full_key, display_name=display,
                value=str(value).lower(),
                field_type=FieldType.TOGGLE, section=section,
            ))
        elif isinstance(value, (int, float)):
            fields.append(ConfigField(
                key=full_key, display_name=display,
                value=str(value),
                field_type=FieldType.TEXT, section=section,
            ))
        else:
            fields.append(ConfigField(
                key=full_key, display_name=display,
                value=str(value) if value is not None else "",
                field_type=FieldType.TEXT, section=section,
            ))
    return fields


def _flatten_json(data, fields: list[ConfigField], prefix: str,
                  section: str = "General") -> None:
    """Flatten a JSON structure into config fields."""
    if isinstance(data, list):
        for i, item in enumerate(data):
            item_key = f"{prefix}[{i}]" if prefix else f"[{i}]"
            if isinstance(item, dict):
                _flatten_json(item, fields, item_key, section)
            else:
                fields.append(ConfigField(
                    key=item_key,
                    display_name=f"Item {i}",
                    value=json.dumps(item) if not isinstance(item, str) else item,
                    field_type=FieldType.TEXT,
                    section=section,
                ))
        return
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                fields.append(ConfigField(
                    key=full_key,
                    display_name=make_display_name(key),
                    value="",
                    field_type=FieldType.COMMENT,
                    section=key.title(),
                ))
                _flatten_json(value, fields, full_key, key.title())
            elif isinstance(value, list):
                fields.append(ConfigField(
                    key=full_key,
                    display_name=make_display_name(key),
                    value=json.dumps(value),
                    field_type=FieldType.MULTILINE,
                    section=section,
                ))
            elif isinstance(value, bool):
                fields.append(ConfigField(
                    key=full_key,
                    display_name=make_display_name(key),
                    value=str(value).lower(),
                    field_type=FieldType.TOGGLE,
                    section=section,
                ))
            elif isinstance(value, (int, float)):
                fields.append(ConfigField(
                    key=full_key,
                    display_name=make_display_name(key),
                    value=str(value),
                    field_type=FieldType.TEXT,
                    section=section,
                ))
            else:
                fields.append(ConfigField(
                    key=full_key,
                    display_name=make_display_name(key),
                    value=str(value),
                    field_type=FieldType.TEXT,
                    section=section,
                ))
