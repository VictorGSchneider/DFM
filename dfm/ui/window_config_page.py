"""Per-dotfile configuration page builder."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Pango

from dfm.core.scanner import DotfileEntry
from dfm.core.parser import parse_config
from dfm.ui.window_sidebar import _categorize
from dfm.ui.window_config_page_fields import create_field_row
from dfm.ui.window_config_page_handlers import (
    on_toggle_changed, on_scale_changed, on_color_changed,
    on_spin_changed, on_text_field_changed, on_browse_path,
)
from dfm.ui.window_config_page_sections import (
    build_actions, build_validation, build_deps,
    build_notes, build_backup_section,
)


class ConfigPageBuilder:
    def __init__(self, window):
        self._window = window
        self._debounce_sources: dict[str, int] = {}

    def build(self, entry: DotfileEntry) -> Gtk.Widget:
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True,
        )
        clamp = Adw.Clamp(maximum_size=800, margin_start=12, margin_end=12,
                          margin_top=12, margin_bottom=24)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        box.append(self._build_breadcrumbs(entry))
        box.append(self._build_title(entry))
        box.append(build_actions(self, entry))
        box.append(build_validation(entry))

        fields_group = Adw.PreferencesGroup(title="Configuration")
        self._populate_fields(fields_group, entry)
        box.append(fields_group)

        deps_widget = build_deps(entry)
        if deps_widget is not None:
            box.append(deps_widget)

        box.append(build_backup_section(self, entry))
        box.append(build_notes(self, entry))

        clamp.set_child(box)
        scrolled.set_child(clamp)
        return scrolled

    def _build_breadcrumbs(self, entry: DotfileEntry) -> Gtk.Widget:
        category = _categorize(entry)
        crumb_label = Gtk.Label(
            label=f"{category}  >  {entry.display_name}", xalign=0,
        )
        crumb_label.add_css_class("dim-label")
        crumb_label.add_css_class("caption")
        return crumb_label

    def _build_title(self, entry: DotfileEntry) -> Gtk.Widget:
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                            margin_top=4)
        icon = Gtk.Image.new_from_icon_name("document-properties-symbolic")
        icon.set_pixel_size(32)
        icon.add_css_class("dim-label")
        title_box.append(icon)

        title_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name_label = Gtk.Label(label=entry.display_name, xalign=0)
        name_label.add_css_class("title-1")
        title_inner.append(name_label)

        path_label = Gtk.Label(label=str(entry.path), xalign=0, selectable=True,
                               ellipsize=Pango.EllipsizeMode.MIDDLE)
        path_label.add_css_class("dim-label")
        path_label.add_css_class("caption")
        title_inner.append(path_label)
        title_box.append(title_inner)
        return title_box

    def _populate_fields(self, container, entry: DotfileEntry):
        parsed = parse_config(entry.get_config_path() or entry.path)
        fields = getattr(parsed, "fields", [])
        if not fields:
            row = Adw.ActionRow(title="No configurable fields detected")
            row.add_css_class("dim-label")
            container.add(row)
            return

        for field in fields:
            row = create_field_row(self, field, parsed, entry)
            if row is not None:
                container.add(row)

    # ── Field change handlers (delegated) ────────────────────────────

    def _on_toggle_changed(self, row, _pspec):
        on_toggle_changed(self, row, _pspec)

    def _on_scale_changed(self, scale):
        on_scale_changed(self, scale)

    def _on_color_changed(self, btn, _pspec):
        on_color_changed(self, btn, _pspec)

    def _on_spin_changed(self, spin):
        on_spin_changed(self, spin)

    def _on_text_field_changed(self, widget):
        on_text_field_changed(self, widget)

    def _on_browse_path(self, btn):
        on_browse_path(self, btn)
