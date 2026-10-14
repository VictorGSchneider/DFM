"""Recognise `name {` ... `}` blocks (Hyprland, rofi, i3, picom, ...)."""

import re

_OPEN = re.compile(r"^([^=:;{}#]+?)\s*:?\s*\{\s*$")
_CLOSE = re.compile(r"^\}\s*;?\s*$")


def block_open(stripped: str) -> str | None:
    """Name of the block a line opens (`general {` -> "general"), else None."""
    match = _OPEN.match(stripped)
    return match.group(1).strip() if match else None


def is_block_close(stripped: str) -> bool:
    return bool(_CLOSE.match(stripped))
