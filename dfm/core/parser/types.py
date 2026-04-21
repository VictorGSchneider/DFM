"""Types and constants for the config parser."""

import re
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
