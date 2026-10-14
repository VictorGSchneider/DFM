"""Pango markup helpers.

Adw row titles/subtitles parse Pango markup, so any text that comes from a
config file, a commit message, a profile name, a path, ... must be escaped
before it is handed to them or '&' and '<' break the whole label.
"""

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib


def esc(text) -> str:
    """Escape `text` for safe use in an Adw/Gtk markup-enabled label."""
    return GLib.markup_escape_text("" if text is None else str(text))
