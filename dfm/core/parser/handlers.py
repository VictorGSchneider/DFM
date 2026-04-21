"""Format-specific parsers: aggregator module."""

from dfm.core.parser.handlers_basic import (
    parse_ini,
    parse_xresources,
    parse_generic,
)
from dfm.core.parser.handlers_structured import (
    parse_toml,
    parse_yaml,
    parse_json,
)
from dfm.core.parser.handlers_shell import parse_shell, parse_i3_like

__all__ = [
    "parse_ini",
    "parse_toml",
    "parse_yaml",
    "parse_shell",
    "parse_xresources",
    "parse_i3_like",
    "parse_json",
    "parse_generic",
]
