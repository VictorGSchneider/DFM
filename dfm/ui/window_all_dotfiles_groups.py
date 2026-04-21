"""Helpers to build per-category group widgets for the All Dotfiles page."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from dfm.core.scanner import DotfileEntry
from dfm.core.conflicts import detect_conflicts
from dfm.ui.window_sidebar import (
    SortMode, SORT_LABELS, CATEGORY_ICONS,
    _group_by_category, _sort_entries,
)


def build_groups(page) -> None:
    """Build category groups with per-group toggles and sort."""
    groups = _group_by_category(page.dotfiles)
    for category in sorted(groups.keys()):
        _build_group(page, category, groups[category])


def _build_group(page, category: str, entries: list[DotfileEntry]) -> None:
    """Build a single category group."""
    sort_mode = page.group_sort_modes.get(category, page.global_sort_mode)
    sorted_entries = _sort_entries(entries, sort_mode)

    enabled_count = sum(1 for e in entries if e.enabled)
    total_count = len(entries)

    group = Adw.PreferencesGroup()
    icon_name = CATEGORY_ICONS.get(category, "application-x-executable-symbolic")

    header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    header_box.set_margin_top(4)
    header_box.set_margin_bottom(4)

    cat_icon = Gtk.Image.new_from_icon_name(icon_name)
    cat_icon.add_css_class("dim-label")
    header_box.append(cat_icon)

    title_label = Gtk.Label(label=category)
    title_label.add_css_class("heading")
    title_label.set_hexpand(True)
    title_label.set_halign(Gtk.Align.START)
    header_box.append(title_label)

    count_label = Gtk.Label(label=f"{enabled_count}/{total_count} enabled")
    count_label.add_css_class("dim-label")
    count_label.add_css_class("caption")
    header_box.append(count_label)

    group.set_header_suffix(header_box)
    group.set_title(category)

    toggle_row = Adw.ActionRow()
    toggle_row.set_title(f"Enable All {category}")

    group_check = Gtk.CheckButton()
    group_check.set_valign(Gtk.Align.CENTER)
    page._group_checks[category] = group_check

    toggle_row.add_suffix(group_check)
    toggle_row.set_activatable_widget(group_check)
    group.add(toggle_row)

    group.add(_build_sort_row(page, category))

    switch_rows = []
    for entry in sorted_entries:
        row = Adw.SwitchRow()
        row.set_title(entry.display_name)
        row.set_subtitle(entry.path)
        row.set_icon_name(entry.icon_name)
        row.set_active(entry.enabled)
        row._dfm_entry = entry
        row.connect("notify::active", page._on_switch_row_toggled, entry)
        switch_rows.append(row)
        group.add(row)

    page._group_switch_rows[category] = switch_rows

    page._update_group_check_state(category)
    group_check.connect("toggled", page._on_group_toggled, category)

    page._content_box.append(group)


def _build_sort_row(page, category: str) -> Adw.ActionRow:
    sort_row = Adw.ActionRow()
    sort_row.set_title("Sort Order")
    sort_row.set_subtitle("Override global sort for this group")

    sort_dropdown = Gtk.DropDown()
    sort_model = Gtk.StringList()
    sort_model.append("Use Global Default")
    for mode in SortMode:
        sort_model.append(SORT_LABELS[mode])
    sort_dropdown.set_model(sort_model)

    if category in page.group_sort_modes:
        sort_dropdown.set_selected(
            list(SortMode).index(page.group_sort_modes[category]) + 1
        )
    else:
        sort_dropdown.set_selected(0)

    sort_dropdown.set_valign(Gtk.Align.CENTER)
    sort_dropdown.connect(
        "notify::selected", page._on_group_sort_changed, category,
    )
    sort_row.add_suffix(sort_dropdown)
    return sort_row


def build_conflict_section(page) -> None:
    """Build the conflict detection section."""
    conflicts = detect_conflicts(page.dotfiles)
    if not conflicts:
        return

    group = Adw.PreferencesGroup()
    group.set_title("Conflicts Detected")
    group.set_description(
        f"{len(conflicts)} potential conflict(s) found between enabled dotfiles"
    )

    severity_map = {
        "error": ("dialog-error-symbolic", "error"),
        "warning": ("dialog-warning-symbolic", "warning"),
    }

    for conflict in conflicts:
        row = Adw.ActionRow()
        row.set_title(conflict.description)
        row.set_subtitle(", ".join(conflict.entries))

        icon_name, css_class = severity_map.get(
            conflict.severity, ("dialog-information-symbolic", "accent"),
        )

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.add_css_class(css_class)
        row.add_prefix(icon)
        group.add(row)

    page._content_box.append(group)
