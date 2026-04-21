"""All Dotfiles overview page - GTK4/Adwaita module for managing all dotfiles."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from dfm.core.scanner import DotfileEntry
from dfm.ui.window_sidebar import SortMode, SORT_LABELS, _categorize
from dfm.ui.window_all_dotfiles_groups import (
    build_groups, build_conflict_section,
)


class AllDotfilesPage:
    """Overview page showing all dotfiles grouped by category with toggles."""

    def __init__(self, on_dotfile_toggled_cb=None, on_rescan_cb=None):
        """Initialize the page.

        Args:
            on_dotfile_toggled_cb: Callback when any toggle changes.
                Signature: (entry: DotfileEntry, new_state: bool) -> None
            on_rescan_cb: Callback to trigger a full rescan from disk.
        """
        self._on_dotfile_toggled_cb = on_dotfile_toggled_cb
        self._on_rescan_cb = on_rescan_cb
        self._master_check: Gtk.CheckButton = Gtk.CheckButton()
        self._group_checks: dict[str, Gtk.CheckButton] = {}
        self._group_switch_rows: dict[str, list[Adw.SwitchRow]] = {}
        self._updating_toggles: bool = False
        self.global_sort_mode: SortMode = SortMode.NAME_ASC
        self.group_sort_modes: dict[str, SortMode] = {}
        self.dotfiles: list[DotfileEntry] = []

        self._scrolled: Gtk.ScrolledWindow | None = None
        self._content_box: Gtk.Box | None = None
        self._clamp: Adw.Clamp | None = None
        self._file_monitor_bar: Adw.Banner | None = None
        self._outer_box: Gtk.Box | None = None

    def build(self, dotfiles: list[DotfileEntry]) -> Gtk.Widget:
        """Build the full scrolled page widget."""
        self.dotfiles = dotfiles

        self._outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self._file_monitor_bar = Adw.Banner()
        self._file_monitor_bar.set_title(
            "External changes detected in dotfiles. Refresh to update."
        )
        self._file_monitor_bar.set_button_label("Refresh")
        self._file_monitor_bar.set_revealed(False)
        self._file_monitor_bar.connect(
            "button-clicked", self._on_monitor_refresh_clicked,
        )
        self._outer_box.append(self._file_monitor_bar)

        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_vexpand(True)
        self._scrolled.set_hexpand(True)
        self._scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._clamp = Adw.Clamp()
        self._clamp.set_maximum_size(700)
        self._clamp.set_tightening_threshold(500)

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._content_box.set_margin_top(16)
        self._content_box.set_margin_bottom(16)
        self._content_box.set_margin_start(16)
        self._content_box.set_margin_end(16)

        self._build_content()

        self._clamp.set_child(self._content_box)
        self._scrolled.set_child(self._clamp)
        self._outer_box.append(self._scrolled)

        return self._outer_box

    def rebuild(self, dotfiles: list[DotfileEntry]) -> None:
        """Rebuild the page content with updated dotfile data."""
        self.dotfiles = dotfiles
        if self._content_box is None:
            return

        child = self._content_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self._content_box.remove(child)
            child = next_child

        self._group_checks.clear()
        self._group_switch_rows.clear()

        self._build_content()

        if self._file_monitor_bar is not None:
            self._file_monitor_bar.set_revealed(False)

    def show_monitor_notification(self) -> None:
        """Show the file monitor notification bar."""
        if self._file_monitor_bar is not None:
            self._file_monitor_bar.set_revealed(True)

    def hide_monitor_notification(self) -> None:
        """Hide the file monitor notification bar."""
        if self._file_monitor_bar is not None:
            self._file_monitor_bar.set_revealed(False)

    # ── Internal UI Construction ─────────────────────────────────────

    def _build_content(self) -> None:
        """Build all content inside the content box."""
        self._build_master_controls()
        build_groups(self)
        build_conflict_section(self)

    def _build_master_controls(self) -> None:
        """Build the master toggle and global sort controls."""
        controls_group = Adw.PreferencesGroup()
        controls_group.set_title("All Dotfiles")
        controls_group.set_description(
            f"{sum(1 for d in self.dotfiles if d.enabled)}/{len(self.dotfiles)} dotfiles enabled"
        )

        master_row = Adw.ActionRow()
        master_row.set_title("Enable All Dotfiles")
        master_row.set_subtitle("Master toggle for all dotfiles")
        master_row.set_icon_name("emblem-default-symbolic")

        self._master_check = Gtk.CheckButton()
        self._master_check.set_valign(Gtk.Align.CENTER)
        self._update_master_check_state()
        self._master_check.connect("toggled", self._on_master_toggled)
        master_row.add_suffix(self._master_check)
        master_row.set_activatable_widget(self._master_check)

        controls_group.add(master_row)

        sort_row = Adw.ActionRow()
        sort_row.set_title("Default Sort Order")
        sort_row.set_subtitle("Applied to all groups unless overridden")
        sort_row.set_icon_name("view-sort-descending-symbolic")

        sort_dropdown = Gtk.DropDown()
        sort_model = Gtk.StringList()
        for mode in SortMode:
            sort_model.append(SORT_LABELS[mode])
        sort_dropdown.set_model(sort_model)
        sort_dropdown.set_selected(list(SortMode).index(self.global_sort_mode))
        sort_dropdown.set_valign(Gtk.Align.CENTER)
        sort_dropdown.connect("notify::selected", self._on_global_sort_changed)
        sort_row.add_suffix(sort_dropdown)

        controls_group.add(sort_row)

        self._content_box.append(controls_group)

    # ── Master Toggle Logic ──────────────────────────────────────────

    def _update_master_check_state(self) -> None:
        """Update master check button to reflect current dotfile states."""
        if not self.dotfiles:
            self._master_check.set_active(False)
            self._master_check.set_inconsistent(False)
            return

        all_enabled = all(d.enabled for d in self.dotfiles)
        none_enabled = not any(d.enabled for d in self.dotfiles)

        if all_enabled:
            self._master_check.set_inconsistent(False)
            self._master_check.set_active(True)
        elif none_enabled:
            self._master_check.set_inconsistent(False)
            self._master_check.set_active(False)
        else:
            self._master_check.set_inconsistent(True)

    def _on_master_toggled(self, check_button: Gtk.CheckButton) -> None:
        """Handle master toggle changes."""
        if self._updating_toggles:
            return

        self._updating_toggles = True
        try:
            new_state = check_button.get_active()
            check_button.set_inconsistent(False)

            for entry in self.dotfiles:
                if entry.enabled != new_state:
                    entry.enabled = new_state
                    if self._on_dotfile_toggled_cb:
                        self._on_dotfile_toggled_cb(entry, new_state)

            for category, group_check in self._group_checks.items():
                group_check.set_inconsistent(False)
                group_check.set_active(new_state)

                for row in self._group_switch_rows.get(category, []):
                    row.set_active(new_state)
        finally:
            self._updating_toggles = False

    # ── Group Toggle Logic ───────────────────────────────────────────

    def _update_group_check_state(self, category: str) -> None:
        """Update a group's check button to reflect its members' states."""
        group_check = self._group_checks.get(category)
        if group_check is None:
            return

        rows = self._group_switch_rows.get(category, [])
        if not rows:
            group_check.set_active(False)
            group_check.set_inconsistent(False)
            return

        states = [row.get_active() for row in rows]
        all_on = all(states)
        all_off = not any(states)

        if all_on:
            group_check.set_inconsistent(False)
            group_check.set_active(True)
        elif all_off:
            group_check.set_inconsistent(False)
            group_check.set_active(False)
        else:
            group_check.set_inconsistent(True)

    def _on_group_toggled(self, check_button: Gtk.CheckButton, category: str) -> None:
        """Handle group toggle changes."""
        if self._updating_toggles:
            return

        self._updating_toggles = True
        try:
            new_state = check_button.get_active()
            check_button.set_inconsistent(False)

            for row in self._group_switch_rows.get(category, []):
                entry = row._dfm_entry
                if entry.enabled != new_state:
                    entry.enabled = new_state
                    row.set_active(new_state)
                    if self._on_dotfile_toggled_cb:
                        self._on_dotfile_toggled_cb(entry, new_state)

            self._update_master_check_state()
        finally:
            self._updating_toggles = False

    # ── Individual Toggle Logic ──────────────────────────────────────

    def _on_switch_row_toggled(self, row: Adw.SwitchRow, _pspec,
                               entry: DotfileEntry) -> None:
        """Handle individual dotfile switch toggle."""
        if self._updating_toggles:
            return

        self._updating_toggles = True
        try:
            new_state = row.get_active()
            entry.enabled = new_state

            if self._on_dotfile_toggled_cb:
                self._on_dotfile_toggled_cb(entry, new_state)

            category = _categorize(entry)
            self._update_group_check_state(category)
            self._update_master_check_state()
        finally:
            self._updating_toggles = False

    # ── Sort Logic ───────────────────────────────────────────────────

    def _on_global_sort_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        """Handle global sort dropdown change."""
        selected = dropdown.get_selected()
        modes = list(SortMode)
        if 0 <= selected < len(modes):
            self.global_sort_mode = modes[selected]
            self.rebuild(self.dotfiles)

    def _on_group_sort_changed(self, dropdown: Gtk.DropDown, _pspec,
                               category: str) -> None:
        """Handle per-group sort dropdown change."""
        selected = dropdown.get_selected()
        if selected == 0:
            self.group_sort_modes.pop(category, None)
        else:
            modes = list(SortMode)
            idx = selected - 1
            if 0 <= idx < len(modes):
                self.group_sort_modes[category] = modes[idx]

        self.rebuild(self.dotfiles)

    # ── File Monitor ─────────────────────────────────────────────────

    def _on_monitor_refresh_clicked(self, _banner: Adw.Banner) -> None:
        """Handle refresh button click on the monitor notification bar."""
        if self._on_rescan_cb is not None:
            self._on_rescan_cb()
        else:
            self.rebuild(self.dotfiles)
