"""Read and write colour values without changing how the file spells them."""

import re

_HEX = re.compile(r"^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
# Hyprland: rgb(rrggbb) / rgba(rrggbbaa), hex digits and no commas
_HYPRLAND = re.compile(r"^(rgba?)\(([0-9a-fA-F]{6}|[0-9a-fA-F]{8})\)$")
# CSS: rgb(r, g, b) / rgba(r, g, b, a)
_CSS = re.compile(
    r"^(rgba?)\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*([0-9.]+)\s*)?\)$"
)

RGBA = tuple[float, float, float, float]


def parse_color(value: str) -> RGBA | None:
    """(r, g, b, a) as floats 0..1, or None if `value` is not a single colour."""
    value = value.strip()

    match = _HEX.match(value)
    if match:
        digits = match.group(1)
        if len(digits) in (3, 4):
            digits = "".join(c * 2 for c in digits)
        return _from_hex(digits)

    match = _HYPRLAND.match(value)
    if match:
        return _from_hex(match.group(2))

    match = _CSS.match(value)
    if match:
        r, g, b = (min(int(match.group(i)), 255) / 255 for i in (2, 3, 4))
        alpha = float(match.group(5)) if match.group(5) else 1.0
        return (r, g, b, min(max(alpha, 0.0), 1.0))
    return None


def format_color(old_value: str, r: float, g: float, b: float, a: float = 1.0) -> str:
    """Render a colour the way `old_value` was written (hex, Hyprland or CSS)."""
    old = old_value.strip()
    rr, gg, bb, aa = (_byte(c) for c in (r, g, b, a))

    match = _HEX.match(old)
    if match:
        has_alpha = len(match.group(1)) in (4, 8)
        return f"#{rr:02x}{gg:02x}{bb:02x}" + (f"{aa:02x}" if has_alpha else "")

    match = _HYPRLAND.match(old)
    if match:
        if match.group(1) == "rgba":
            return f"rgba({rr:02x}{gg:02x}{bb:02x}{aa:02x})"
        return f"rgb({rr:02x}{gg:02x}{bb:02x})"

    match = _CSS.match(old)
    if match:
        if match.group(1) == "rgba":
            return f"rgba({rr}, {gg}, {bb}, {min(max(a, 0.0), 1.0):g})"
        return f"rgb({rr}, {gg}, {bb})"

    return f"#{rr:02x}{gg:02x}{bb:02x}"


def _from_hex(digits: str) -> RGBA:
    channels = [int(digits[i:i + 2], 16) / 255 for i in range(0, len(digits), 2)]
    if len(channels) == 3:
        channels.append(1.0)
    return tuple(channels)  # type: ignore[return-value]


def _byte(channel: float) -> int:
    return min(max(round(channel * 255), 0), 255)
