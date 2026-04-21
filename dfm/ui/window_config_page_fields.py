"""Build individual UI rows for each ConfigField type."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk

from dfm.core.parser import ConfigField, FieldType, ParsedConfig, BOOL_TRUE
from dfm.core.scanner import DotfileEntry


def auto_range(key: str, current_val: float) -> tuple[float, float, float]:
    """Pick a reasonable (lo, hi, step) for a numeric key."""
    key_lower = key.lower()
    if "opacity" in key_lower or "alpha" in key_lower or "dim" in key_lower:
        return (0.0, 1.0, 0.05)
    if "gap" in key_lower or "margin" in key_lower or "padding" in key_lower:
        return (0, max(50, current_val * 2), 1)
    if "border" in key_lower or "radius" in key_lower or "rounding" in key_lower:
        return (0, max(30, current_val * 2), 1)
    if "size" in key_lower or "width" in key_lower or "height" in key_lower:
        return (0, max(200, current_val * 2), 1)
    if "speed" in key_lower or "rate" in key_lower:
        return (0, max(100, current_val * 2), 1)
    if "delay" in key_lower or "timeout" in key_lower or "interval" in key_lower:
        return (0, max(10000, current_val * 2), 100)
    if "scale" in key_lower:
        return (0.5, 3.0, 0.1)
    if "blur" in key_lower:
        return (0, max(20, current_val * 2), 1)
    if "columns" in key_lower or "rows" in key_lower:
        return (1, max(20, current_val * 2), 1)
    return (0, max(100, current_val * 2), 1)


def _attach(widget, field, parsed, entry):
    widget._field = field
    widget._parsed = parsed
    widget._entry = entry


def create_field_row(builder, field: ConfigField, parsed: ParsedConfig,
                     entry: DotfileEntry) -> Adw.ActionRow | None:
    """Create a row widget appropriate for the field's type."""
    ftype = field.field_type if hasattr(field, "field_type") else getattr(field, "type", None)
    key = field.key
    value = field.value
    description = getattr(field, "comment", "") or ""

    if ftype == FieldType.COMMENT:
        return None

    if ftype == FieldType.TOGGLE:
        row = Adw.SwitchRow(title=key, subtitle=description)
        is_on = str(value).lower() in [v.lower() for v in BOOL_TRUE]
        row.set_active(is_on)
        _attach(row, field, parsed, entry)
        row.connect("notify::active", builder._on_toggle_changed)
        return row

    if ftype == FieldType.SLIDER:
        return _slider_row(builder, field, parsed, entry, key, value, description)

    if ftype == FieldType.COLOR:
        return _color_row(builder, field, parsed, entry, key, value, description)

    if ftype == FieldType.NUMBER:
        return _number_row(builder, field, parsed, entry, key, value, description)

    if ftype == FieldType.PATH:
        return _path_row(builder, field, parsed, entry, key, value, description)

    if ftype == FieldType.KEYBIND:
        row = Adw.ActionRow(title=key, subtitle=description)
        label = Gtk.Label(label=str(value) if value else "",
                          selectable=True, valign=Gtk.Align.CENTER)
        label.add_css_class("monospace")
        row.add_suffix(label)
        return row

    if ftype == FieldType.FONT:
        return _text_row(builder, field, parsed, entry, key, value, description)

    return _text_row(builder, field, parsed, entry, key, value, description)


def _slider_row(builder, field, parsed, entry, key, value, description):
    row = Adw.ActionRow(title=key, subtitle=description)
    try:
        current = float(value)
    except (TypeError, ValueError):
        current = 0.0
    lo, hi, step = auto_range(key, current)
    adj = Gtk.Adjustment(value=current, lower=lo, upper=hi,
                         step_increment=step, page_increment=step * 10)
    scale = Gtk.Scale(
        orientation=Gtk.Orientation.HORIZONTAL,
        adjustment=adj,
        draw_value=True,
        digits=2 if step < 1 else 0,
        hexpand=True,
        valign=Gtk.Align.CENTER,
    )
    scale.set_size_request(200, -1)
    _attach(scale, field, parsed, entry)
    scale.connect("value-changed", builder._on_scale_changed)
    row.add_suffix(scale)
    return row


def _color_row(builder, field, parsed, entry, key, value, description):
    row = Adw.ActionRow(title=key, subtitle=description)
    rgba = Gdk.RGBA()
    color_str = str(value) if value else "#000000"
    if not rgba.parse(color_str):
        rgba.parse("#000000")
    color_dialog = Gtk.ColorDialog()
    color_btn = Gtk.ColorDialogButton(dialog=color_dialog, valign=Gtk.Align.CENTER)
    color_btn.set_rgba(rgba)
    _attach(color_btn, field, parsed, entry)
    color_btn.connect("notify::rgba", builder._on_color_changed)
    row.add_suffix(color_btn)
    return row


def _number_row(builder, field, parsed, entry, key, value, description):
    row = Adw.ActionRow(title=key, subtitle=description)
    try:
        current = float(value)
    except (TypeError, ValueError):
        current = 0.0
    lo, hi, step = auto_range(key, current)
    adj = Gtk.Adjustment(value=current, lower=lo, upper=hi,
                         step_increment=step, page_increment=step * 10)
    spin = Gtk.SpinButton(adjustment=adj, climb_rate=1,
                          digits=2 if step < 1 else 0,
                          valign=Gtk.Align.CENTER)
    _attach(spin, field, parsed, entry)
    spin.connect("value-changed", builder._on_spin_changed)
    row.add_suffix(spin)
    return row


def _path_row(builder, field, parsed, entry, key, value, description):
    row = Adw.ActionRow(title=key, subtitle=description)
    path_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4,
                       valign=Gtk.Align.CENTER)
    path_entry = Gtk.Entry(text=str(value) if value else "",
                           hexpand=True, valign=Gtk.Align.CENTER)
    path_entry.set_size_request(200, -1)
    _attach(path_entry, field, parsed, entry)
    path_entry.connect("changed", builder._on_text_field_changed)
    path_box.append(path_entry)

    browse_btn = Gtk.Button(icon_name="folder-open-symbolic",
                            valign=Gtk.Align.CENTER,
                            tooltip_text="Browse")
    browse_btn.add_css_class("flat")
    browse_btn._path_entry = path_entry
    browse_btn.connect("clicked", builder._on_browse_path)
    path_box.append(browse_btn)
    row.add_suffix(path_box)
    return row


def _text_row(builder, field, parsed, entry, key, value, description):
    row = Adw.ActionRow(title=key, subtitle=description)
    text_entry = Gtk.Entry(text=str(value) if value else "",
                           valign=Gtk.Align.CENTER, hexpand=True)
    text_entry.set_size_request(200, -1)
    _attach(text_entry, field, parsed, entry)
    text_entry.connect("changed", builder._on_text_field_changed)
    row.add_suffix(text_entry)
    return row
