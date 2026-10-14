"""Field-change handlers for the config page builder.

Each handler debounces writes through a backup + update cycle so rapid
edits don't spam the disk.
"""

import os
import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio, GLib, Adw

from dfm.core.backup import create_backup
from dfm.core.parser import update_config_value
from dfm.core.parser.colors import format_color
from dfm.core.parser.toggles import toggle_value


def _toast(builder, message: str) -> None:
    overlay = getattr(builder._window, "_toast_overlay", None)
    if overlay is not None:
        overlay.add_toast(Adw.Toast.new(message))


def update_monitor(builder, config_path: str) -> None:
    """Tell the file monitor we made the change ourselves."""
    monitor = getattr(builder._window, "_monitor", None)
    if monitor is not None:
        monitor.update_state(str(config_path))


def _debounced_save(builder, widget, new_val: str, prefix: str, delay: int = 500):
    field = widget._field
    entry = widget._entry
    config_path = entry.get_config_path() or entry.path
    key = f"{prefix}-{id(widget)}"

    if key in builder._debounce_sources:
        GLib.source_remove(builder._debounce_sources[key])

    def _save():
        create_backup(str(config_path), "edit")
        if update_config_value(config_path, field, new_val):
            # The widget keeps this field for later edits: track what's on disk
            field.value = new_val
        else:
            _toast(builder, f"Couldn't save '{field.key}': its line changed or "
                            "can't be edited here")
        update_monitor(builder, config_path)
        builder._debounce_sources.pop(key, None)
        return False

    builder._debounce_sources[key] = GLib.timeout_add(delay, _save)


def on_toggle_changed(builder, row, _pspec):
    new_val = toggle_value(row._field.value, row.get_active())
    _debounced_save(builder, row, new_val, "toggle", delay=300)


def on_scale_changed(builder, scale):
    raw = scale.get_value()
    new_val = str(int(raw)) if raw == int(raw) else str(raw)
    _debounced_save(builder, scale, new_val, "scale")


def on_color_changed(builder, btn, _pspec):
    rgba = btn.get_rgba()
    new_color = format_color(btn._field.value, rgba.red, rgba.green,
                             rgba.blue, rgba.alpha)
    _debounced_save(builder, btn, new_color, "color")


def on_spin_changed(builder, spin):
    raw = spin.get_value()
    new_val = str(int(raw)) if raw == int(raw) else str(raw)
    _debounced_save(builder, spin, new_val, "spin")


def on_text_field_changed(builder, widget):
    _debounced_save(builder, widget, widget.get_text(), "text")


def on_browse_path(builder, btn):
    path_entry = btn._path_entry
    dialog = Gtk.FileDialog()
    current = path_entry.get_text()
    if current and os.path.exists(current):
        dialog.set_initial_file(Gio.File.new_for_path(current))
    dialog.open(builder._window, None, _on_browse_finish, path_entry)


def _on_browse_finish(dialog, result, path_entry):
    try:
        f = dialog.open_finish(result)
        if f:
            path_entry.set_text(f.get_path())
    except GLib.Error as e:
        if e.code != 2:
            print(f"DFM browse error: {e}", file=sys.stderr)
