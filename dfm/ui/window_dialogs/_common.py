"""Shared helpers for dialog classes."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def clear_box(box: Gtk.Box) -> None:
    """Remove all children from a Gtk.Box."""
    while True:
        child = box.get_first_child()
        if child is None:
            break
        box.remove(child)


def make_dialog(title: str, width: int = 700, height: int = 500):
    """Create an Adw.Dialog (libadwaita 1.5+) or fall back to Adw.Window."""
    try:
        dialog = Adw.Dialog()
        dialog.set_title(title)
        dialog.set_content_width(width)
        dialog.set_content_height(height)
        return dialog
    except (TypeError, AttributeError):
        win = Adw.Window()
        win.set_title(title)
        win.set_default_size(width, height)
        win.set_modal(True)
        return win


def present_dialog(dialog, parent_window) -> None:
    """Present the dialog, handling both Adw.Dialog and Adw.Window."""
    if isinstance(dialog, Adw.Dialog):
        dialog.present(parent_window)
    else:
        if parent_window is not None:
            dialog.set_transient_for(parent_window)
        dialog.present()


def set_dialog_content(dialog, content) -> None:
    """Set the main content widget of a dialog or window."""
    if isinstance(dialog, Adw.Dialog):
        dialog.set_child(content)
    else:
        dialog.set_content(content)


class StatusMixin:
    """Mixin adding a dim status label with auto-hide."""

    _status_label: Gtk.Label

    def _show_status(self, message: str) -> None:
        self._status_label.set_label(message)
        self._status_label.set_visible(True)
        GLib.timeout_add(5000, self._hide_status)

    def _hide_status(self):
        self._status_label.set_visible(False)
        return False
