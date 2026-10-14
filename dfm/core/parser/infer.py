"""Heuristics for inferring field types and display names."""

from dfm.core.parser.types import (
    FieldType, BOOL_TRUE, BOOL_FALSE, COLOR_PATTERN, PATH_PATTERN,
    KEYBIND_KEYWORDS, SLIDER_KEYS,
)


_BOOLISH_KEY = ("enable", "disable", "use_", "is_", "has_", "show", "hide",
                "allow", "no_", "smart", "auto")


def _is_numeric_key(key_lower: str) -> bool:
    if key_lower.startswith(_BOOLISH_KEY) or any(
            part in key_lower for part in _BOOLISH_KEY[:2]):
        return False
    return any(s in key_lower for s in SLIDER_KEYS)


def infer_field_type(key: str, value: str) -> FieldType:
    """Infer the best UI field type from a key-value pair."""
    val_lower = value.lower().strip()
    key_lower = key.lower().replace("-", "_").replace(".", "_")

    if val_lower in BOOL_TRUE or val_lower in BOOL_FALSE:
        # "0"/"1" next to a numeric-looking key (border_size, gaps_in, ...) is a
        # number that happens to be 0 or 1, not an on/off switch
        if not (val_lower in ("0", "1") and _is_numeric_key(key_lower)):
            return FieldType.TOGGLE

    if COLOR_PATTERN.match(value.strip()):
        return FieldType.COLOR

    try:
        float(value.strip())
        key_parts = set(key_lower.replace("_", " ").replace("-", " ").split())
        if key_parts & SLIDER_KEYS or any(s in key_lower for s in SLIDER_KEYS):
            return FieldType.SLIDER
        return FieldType.NUMBER
    except ValueError:
        pass

    if PATH_PATTERN.match(value.strip()) or "path" in key_lower or "dir" in key_lower:
        stripped = value.strip()
        if stripped.startswith(("/", "~", "$HOME")):
            return FieldType.PATH

    if "font" in key_lower:
        return FieldType.FONT

    key_parts_set = set(key_lower.replace("_", " ").replace("-", " ").split())
    if key_parts_set & KEYBIND_KEYWORDS:
        return FieldType.KEYBIND

    return FieldType.TEXT


def make_display_name(key: str) -> str:
    """Convert a config key into a human-readable display name."""
    name = key
    for prefix in ("set ", "set-", "setopt ", "unsetopt "):
        if name.lower().startswith(prefix):
            name = name[len(prefix):]
            break

    name = name.replace("_", " ").replace("-", " ").replace(".", " > ")
    return name.strip().title()
