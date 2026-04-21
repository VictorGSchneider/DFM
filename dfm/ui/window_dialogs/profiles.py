"""Save, load, delete, and export configuration profiles."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk

from dfm.core.profiles import (
    list_profiles, save_profile, load_profile,
    delete_profile, export_profile_json,
)
from dfm.ui.window_dialogs._common import (
    make_dialog, present_dialog, set_dialog_content, StatusMixin,
)


class ProfilesDialog(StatusMixin):
    """Manage configuration profiles: save, load, delete, export."""

    def __init__(self, parent_window, dotfiles: list) -> None:
        self.parent_window = parent_window
        self.dotfiles = dotfiles
        self.dialog = make_dialog("Profiles", width=650, height=550)
        self._build_ui()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_title(True)
        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._content_box.set_margin_start(16)
        self._content_box.set_margin_end(16)
        self._content_box.set_margin_top(12)
        self._content_box.set_margin_bottom(12)

        self._content_box.append(self._build_save_group())

        self._profiles_group = Adw.PreferencesGroup()
        self._profiles_group.set_title("Saved Profiles")
        self._content_box.append(self._profiles_group)

        self._status_label = Gtk.Label(label="")
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.add_css_class("dim-label")
        self._status_label.set_visible(False)
        self._status_label.set_wrap(True)
        self._content_box.append(self._status_label)

        scrolled.set_child(self._content_box)
        toolbar_view.set_content(scrolled)
        set_dialog_content(self.dialog, toolbar_view)

        self._refresh_profiles()

    def _build_save_group(self) -> Adw.PreferencesGroup:
        save_group = Adw.PreferencesGroup()
        save_group.set_title("Save Current State")
        save_group.set_description(
            "Save a snapshot of all current dotfile states and configs"
        )

        self._name_entry = Adw.EntryRow()
        self._name_entry.set_title("Profile Name")
        save_group.add(self._name_entry)

        self._desc_entry = Adw.EntryRow()
        self._desc_entry.set_title("Description")
        save_group.add(self._desc_entry)

        save_btn_row = Adw.ActionRow()
        save_btn_row.set_title("Save Current")
        save_btn_row.set_subtitle(f"{len(self.dotfiles)} dotfiles will be saved")
        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.set_valign(Gtk.Align.CENTER)
        save_btn.connect("clicked", self._on_save_clicked)
        save_btn_row.add_suffix(save_btn)
        save_group.add(save_btn_row)
        return save_group

    def _refresh_profiles(self) -> None:
        """Reload and display the profile list."""
        parent = self._profiles_group.get_parent()
        if parent is not None:
            parent.remove(self._profiles_group)

        self._profiles_group = Adw.PreferencesGroup()
        self._profiles_group.set_title("Saved Profiles")

        profiles = list_profiles()
        if not profiles:
            self._profiles_group.set_description("No saved profiles yet")
        else:
            self._profiles_group.set_description(f"{len(profiles)} profile(s) saved")
            for profile in profiles:
                self._profiles_group.add(self._build_profile_row(profile))

        children = []
        child = self._content_box.get_first_child()
        while child is not None:
            children.append(child)
            child = child.get_next_sibling()

        if len(children) >= 2:
            self._content_box.insert_child_after(self._profiles_group, children[0])
        else:
            self._content_box.append(self._profiles_group)

    def _build_profile_row(self, profile) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_title(profile.name)
        subtitle_parts = []
        if profile.description:
            subtitle_parts.append(profile.description)
        subtitle_parts.append(
            f"{profile.dotfile_count} dotfiles | {profile.display_time}"
        )
        row.set_subtitle(" - ".join(subtitle_parts))

        export_btn = Gtk.Button(
            icon_name="document-save-as-symbolic",
            tooltip_text="Export as JSON",
        )
        export_btn.add_css_class("flat")
        export_btn.set_valign(Gtk.Align.CENTER)
        export_btn._profile_name = profile.name
        export_btn.connect("clicked", self._on_export_clicked)
        row.add_suffix(export_btn)

        load_btn = Gtk.Button(label="Load")
        load_btn.add_css_class("flat")
        load_btn.set_valign(Gtk.Align.CENTER)
        load_btn._profile_name = profile.name
        load_btn.connect("clicked", self._on_load_clicked)
        row.add_suffix(load_btn)

        delete_btn = Gtk.Button(
            icon_name="user-trash-symbolic", tooltip_text="Delete profile",
        )
        delete_btn.add_css_class("flat")
        delete_btn.add_css_class("error")
        delete_btn.set_valign(Gtk.Align.CENTER)
        delete_btn._profile_name = profile.name
        delete_btn.connect("clicked", self._on_delete_clicked)
        row.add_suffix(delete_btn)
        return row

    def _on_save_clicked(self, _btn: Gtk.Button) -> None:
        name = self._name_entry.get_text().strip()
        if not name:
            self._show_status("Please enter a profile name.")
            return
        description = self._desc_entry.get_text().strip()
        try:
            profile = save_profile(name, description, self.dotfiles)
            self._name_entry.set_text("")
            self._desc_entry.set_text("")
            self._show_status(
                f"Saved profile '{profile.name}' with "
                f"{profile.dotfile_count} dotfiles."
            )
            self._refresh_profiles()
        except Exception as e:
            self._show_status(f"Error saving profile: {e}")

    def _on_load_clicked(self, btn: Gtk.Button) -> None:
        profile_name = btn._profile_name
        try:
            actions = load_profile(profile_name, self.dotfiles)
            if actions:
                msg = f"Loaded '{profile_name}':\n" + "\n".join(
                    f"  {a}" for a in actions
                )
            else:
                msg = f"Loaded '{profile_name}' (no changes needed)"
            self._show_status(msg)
        except Exception as e:
            self._show_status(f"Error loading profile: {e}")

    def _on_delete_clicked(self, btn: Gtk.Button) -> None:
        profile_name = btn._profile_name
        if delete_profile(profile_name):
            self._show_status(f"Deleted profile '{profile_name}'")
            self._refresh_profiles()
        else:
            self._show_status(f"Could not delete '{profile_name}'")

    def _on_export_clicked(self, btn: Gtk.Button) -> None:
        profile_name = btn._profile_name
        json_str = export_profile_json(profile_name)
        if json_str is None:
            self._show_status(f"Could not export '{profile_name}'")
            return
        Gdk.Display.get_default().get_clipboard().set(json_str)
        self._show_status(
            f"Exported '{profile_name}' to clipboard "
            f"({len(json_str)} characters)"
        )

    def present(self) -> None:
        present_dialog(self.dialog, self.parent_window)
