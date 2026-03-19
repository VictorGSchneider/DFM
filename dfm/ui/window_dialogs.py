"""Dialog classes for profiles, templates, wizard, and diff viewer."""

import os
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Pango, Gdk

from dfm.core.profiles import (
    list_profiles,
    save_profile,
    load_profile,
    delete_profile,
    export_profile_json,
    Profile,
)
from dfm.core.templates import get_templates_by_category, install_template, Template
from dfm.core.wizard import get_available_wizards, run_wizard, WizardApp
from dfm.core.backup import get_backups, restore_backup, get_diff, BackupEntry
from dfm.core.diff_utils import diff_stats


# ── Helpers ──────────────────────────────────────────────────────────


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _clear_box(box: Gtk.Box) -> None:
    """Remove all children from a Gtk.Box."""
    while True:
        child = box.get_first_child()
        if child is None:
            break
        box.remove(child)


def _make_dialog(title: str, width: int = 700, height: int = 500):
    """Create an Adw.Dialog (libadwaita 1.5+) or fall back to Adw.Window."""
    try:
        dialog = Adw.Dialog()
        dialog.set_title(title)
        dialog.set_content_width(width)
        dialog.set_content_height(height)
        return dialog
    except Exception:
        # Fallback for older libadwaita without Adw.Dialog
        win = Adw.Window()
        win.set_title(title)
        win.set_default_size(width, height)
        win.set_modal(True)
        return win


def _present_dialog(dialog, parent_window) -> None:
    """Present the dialog, handling both Adw.Dialog and Adw.Window."""
    if isinstance(dialog, Adw.Dialog):
        dialog.present(parent_window)
    else:
        if parent_window is not None:
            dialog.set_transient_for(parent_window)
        dialog.present()


# ── ProfilesDialog ───────────────────────────────────────────────────


class ProfilesDialog:
    """Manage configuration profiles: save, load, delete, export."""

    def __init__(self, parent_window, dotfiles: list) -> None:
        self.parent_window = parent_window
        self.dotfiles = dotfiles

        self.dialog = _make_dialog("Profiles", width=650, height=550)

        self._build_ui()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()

        # Header
        header = Adw.HeaderBar()
        header.set_show_title(True)
        toolbar_view.add_top_bar(header)

        # Main content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12
        )
        self._content_box.set_margin_start(16)
        self._content_box.set_margin_end(16)
        self._content_box.set_margin_top(12)
        self._content_box.set_margin_bottom(12)

        # -- Save section --
        save_group = Adw.PreferencesGroup()
        save_group.set_title("Save Current State")
        save_group.set_description(
            "Save a snapshot of all current dotfile states and configs"
        )

        # Name entry row
        self._name_entry = Adw.EntryRow()
        self._name_entry.set_title("Profile Name")
        save_group.add(self._name_entry)

        # Description entry row
        self._desc_entry = Adw.EntryRow()
        self._desc_entry.set_title("Description")
        save_group.add(self._desc_entry)

        # Save button row
        save_btn_row = Adw.ActionRow()
        save_btn_row.set_title("Save Current")
        save_btn_row.set_subtitle(f"{len(self.dotfiles)} dotfiles will be saved")
        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.set_valign(Gtk.Align.CENTER)
        save_btn.connect("clicked", self._on_save_clicked)
        save_btn_row.add_suffix(save_btn)
        save_group.add(save_btn_row)

        self._content_box.append(save_group)

        # -- Existing profiles section --
        self._profiles_group = Adw.PreferencesGroup()
        self._profiles_group.set_title("Saved Profiles")
        self._content_box.append(self._profiles_group)

        # Status label
        self._status_label = Gtk.Label(label="")
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.add_css_class("dim-label")
        self._status_label.set_visible(False)
        self._status_label.set_wrap(True)
        self._content_box.append(self._status_label)

        scrolled.set_child(self._content_box)
        toolbar_view.set_content(scrolled)

        if isinstance(self.dialog, Adw.Dialog):
            self.dialog.set_child(toolbar_view)
        else:
            self.dialog.set_content(toolbar_view)

        self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        """Reload and display the profile list."""
        # Clear existing profile rows from the group
        # Rebuild the group entirely
        parent = self._profiles_group.get_parent()
        if parent is not None:
            idx = 0
            child = parent.get_first_child()
            found_idx = 0
            while child is not None:
                if child == self._profiles_group:
                    found_idx = idx
                    break
                idx += 1
                child = child.get_next_sibling()
            parent.remove(self._profiles_group)

        self._profiles_group = Adw.PreferencesGroup()
        self._profiles_group.set_title("Saved Profiles")

        profiles = list_profiles()

        if not profiles:
            self._profiles_group.set_description("No saved profiles yet")
        else:
            self._profiles_group.set_description(
                f"{len(profiles)} profile(s) saved"
            )

            for profile in profiles:
                row = Adw.ActionRow()
                row.set_title(profile.name)
                subtitle_parts = []
                if profile.description:
                    subtitle_parts.append(profile.description)
                subtitle_parts.append(
                    f"{profile.dotfile_count} dotfiles | {profile.display_time}"
                )
                row.set_subtitle(" - ".join(subtitle_parts))

                # Export button
                export_btn = Gtk.Button(
                    icon_name="document-save-as-symbolic",
                    tooltip_text="Export as JSON",
                )
                export_btn.add_css_class("flat")
                export_btn.set_valign(Gtk.Align.CENTER)
                export_btn._profile_name = profile.name
                export_btn.connect("clicked", self._on_export_clicked)
                row.add_suffix(export_btn)

                # Load button
                load_btn = Gtk.Button(label="Load")
                load_btn.add_css_class("flat")
                load_btn.set_valign(Gtk.Align.CENTER)
                load_btn._profile_name = profile.name
                load_btn.connect("clicked", self._on_load_clicked)
                row.add_suffix(load_btn)

                # Delete button
                delete_btn = Gtk.Button(
                    icon_name="user-trash-symbolic",
                    tooltip_text="Delete profile",
                )
                delete_btn.add_css_class("flat")
                delete_btn.add_css_class("error")
                delete_btn.set_valign(Gtk.Align.CENTER)
                delete_btn._profile_name = profile.name
                delete_btn.connect("clicked", self._on_delete_clicked)
                row.add_suffix(delete_btn)

                self._profiles_group.add(row)

        # Re-insert profiles group before the status label
        # Find position: after save_group
        children = []
        child = self._content_box.get_first_child()
        while child is not None:
            children.append(child)
            child = child.get_next_sibling()

        # Insert at position 1 (after save_group, before status label)
        if len(children) >= 2:
            self._content_box.insert_child_after(
                self._profiles_group, children[0]
            )
        else:
            self._content_box.append(self._profiles_group)

    def _show_status(self, message: str) -> None:
        self._status_label.set_label(message)
        self._status_label.set_visible(True)
        GLib.timeout_add(5000, lambda: self._status_label.set_visible(False))

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
        success = delete_profile(profile_name)
        if success:
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

        # Copy to clipboard
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(json_str)
        self._show_status(
            f"Exported '{profile_name}' to clipboard "
            f"({len(json_str)} characters)"
        )

    def present(self) -> None:
        _present_dialog(self.dialog, self.parent_window)


# ── TemplatesDialog ──────────────────────────────────────────────────


class TemplatesDialog:
    """Browse and install pre-made config templates."""

    def __init__(self, parent_window, on_rescan_cb=None) -> None:
        self.parent_window = parent_window
        self.on_rescan_cb = on_rescan_cb

        self.dialog = _make_dialog("Templates", width=750, height=600)

        self._build_ui()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()

        # Header
        header = Adw.HeaderBar()
        header.set_show_title(True)
        toolbar_view.add_top_bar(header)

        # Main scrollable content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12
        )
        content_box.set_margin_start(16)
        content_box.set_margin_end(16)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)

        # Status label (hidden by default)
        self._status_label = Gtk.Label(label="")
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.add_css_class("dim-label")
        self._status_label.set_visible(False)
        self._status_label.set_wrap(True)
        content_box.append(self._status_label)

        # Templates grouped by category
        categories = get_templates_by_category()

        for category, templates in sorted(categories.items()):
            group = Adw.PreferencesGroup()
            group.set_title(category)
            group.set_description(f"{len(templates)} template(s)")

            for template in templates:
                row = Adw.ExpanderRow()
                row.set_title(template.app_name)
                row.set_subtitle(template.description)
                row.set_enable_expansion(True)

                # Preview of content
                preview_row = Adw.ActionRow()
                preview_text_view = Gtk.TextView()
                preview_text_view.set_editable(False)
                preview_text_view.set_cursor_visible(False)
                preview_text_view.set_monospace(True)
                preview_text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

                # Show first 20 lines as preview
                preview_lines = template.content.strip().splitlines()[:20]
                preview_content = "\n".join(preview_lines)
                if len(template.content.strip().splitlines()) > 20:
                    preview_content += "\n..."
                preview_text_view.get_buffer().set_text(preview_content)

                preview_text_view.set_left_margin(12)
                preview_text_view.set_right_margin(12)
                preview_text_view.set_top_margin(8)
                preview_text_view.set_bottom_margin(8)

                preview_frame = Gtk.Frame()
                preview_frame.set_child(preview_text_view)
                preview_frame.set_margin_start(12)
                preview_frame.set_margin_end(12)
                preview_frame.set_margin_top(4)
                preview_frame.set_margin_bottom(4)

                preview_action = Adw.ActionRow()
                preview_action.set_child(preview_frame)
                row.add_row(preview_action)

                # Install destination info
                dest_row = Adw.ActionRow()
                dest_row.set_title("Installs to")
                dest_row.set_subtitle(template.config_path)

                # Install button
                install_btn = Gtk.Button(label="Install")
                install_btn.add_css_class("suggested-action")
                install_btn.set_valign(Gtk.Align.CENTER)
                install_btn._template = template
                install_btn.connect("clicked", self._on_install_clicked)
                dest_row.add_suffix(install_btn)

                row.add_row(dest_row)

                group.add(row)

            content_box.append(group)

        scrolled.set_child(content_box)
        toolbar_view.set_content(scrolled)

        if isinstance(self.dialog, Adw.Dialog):
            self.dialog.set_child(toolbar_view)
        else:
            self.dialog.set_content(toolbar_view)

    def _show_status(self, message: str) -> None:
        self._status_label.set_label(message)
        self._status_label.set_visible(True)
        GLib.timeout_add(5000, lambda: self._status_label.set_visible(False))

    def _on_install_clicked(self, btn: Gtk.Button) -> None:
        template = btn._template
        target = os.path.expanduser(template.config_path)

        if os.path.isfile(target):
            # Warn that existing file will be backed up
            self._confirm_install(template, target)
        else:
            self._do_install(template)

    def _confirm_install(self, template: Template, target: str) -> None:
        """Show a confirmation before overwriting an existing config."""
        confirm_dialog = Adw.AlertDialog()
        confirm_dialog.set_heading("File Exists")
        confirm_dialog.set_body(
            f"The file {target} already exists. "
            f"A backup will be created before overwriting."
        )
        confirm_dialog.add_response("cancel", "Cancel")
        confirm_dialog.add_response("install", "Install Anyway")
        confirm_dialog.set_response_appearance(
            "install", Adw.ResponseAppearance.DESTRUCTIVE
        )
        confirm_dialog.set_default_response("cancel")
        confirm_dialog.set_close_response("cancel")

        confirm_dialog.connect(
            "response", self._on_confirm_response, template
        )

        if isinstance(self.dialog, Adw.Dialog):
            confirm_dialog.present(self.dialog)
        else:
            confirm_dialog.present(self.dialog)

    def _on_confirm_response(
        self, dialog, response: str, template: Template
    ) -> None:
        if response == "install":
            self._do_install(template)

    def _do_install(self, template: Template) -> None:
        try:
            msg = install_template(template, backup=True)
            self._show_status(msg)
            if self.on_rescan_cb is not None:
                self.on_rescan_cb()
        except Exception as e:
            self._show_status(f"Error installing template: {e}")

    def present(self) -> None:
        _present_dialog(self.dialog, self.parent_window)


# ── WizardDialog ─────────────────────────────────────────────────────


class WizardDialog:
    """Generate base configs for installed apps that lack config files."""

    def __init__(self, parent_window, dotfiles: list, on_rescan_cb=None) -> None:
        self.parent_window = parent_window
        self.dotfiles = dotfiles
        self.on_rescan_cb = on_rescan_cb

        self.dialog = _make_dialog("Config Wizard", width=650, height=500)

        self._build_ui()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()

        # Header
        header = Adw.HeaderBar()
        header.set_show_title(True)
        toolbar_view.add_top_bar(header)

        # Main scrollable content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12
        )
        self._content_box.set_margin_start(16)
        self._content_box.set_margin_end(16)
        self._content_box.set_margin_top(12)
        self._content_box.set_margin_bottom(12)

        # Status label
        self._status_label = Gtk.Label(label="")
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.add_css_class("dim-label")
        self._status_label.set_visible(False)
        self._status_label.set_wrap(True)
        self._content_box.append(self._status_label)

        # Discover available wizard apps
        wizards = get_available_wizards(self.dotfiles)

        if not wizards:
            empty_group = Adw.PreferencesGroup()
            empty_group.set_title("No Suggestions")
            empty_group.set_description(
                "All installed applications already have config files, "
                "or no supported applications were detected."
            )
            self._content_box.append(empty_group)
        else:
            # Group by category
            categories: dict[str, list[WizardApp]] = {}
            for app in wizards:
                categories.setdefault(app.category, []).append(app)

            desc_group = Adw.PreferencesGroup()
            desc_group.set_title("Available Configs")
            desc_group.set_description(
                f"{len(wizards)} installed app(s) detected without config files"
            )
            self._content_box.append(desc_group)

            for category, apps in sorted(categories.items()):
                group = Adw.PreferencesGroup()
                group.set_title(category)

                for app in apps:
                    row = Adw.ActionRow()
                    row.set_title(app.display_name)
                    row.set_subtitle(
                        f"{app.description} | {app.config_path}"
                    )

                    generate_btn = Gtk.Button(label="Generate")
                    generate_btn.add_css_class("suggested-action")
                    generate_btn.set_valign(Gtk.Align.CENTER)
                    generate_btn._wizard_app = app
                    generate_btn.connect(
                        "clicked", self._on_generate_clicked
                    )
                    row.add_suffix(generate_btn)

                    group.add(row)

                self._content_box.append(group)

        scrolled.set_child(self._content_box)
        toolbar_view.set_content(scrolled)

        if isinstance(self.dialog, Adw.Dialog):
            self.dialog.set_child(toolbar_view)
        else:
            self.dialog.set_content(toolbar_view)

    def _show_status(self, message: str) -> None:
        self._status_label.set_label(message)
        self._status_label.set_visible(True)
        GLib.timeout_add(5000, lambda: self._status_label.set_visible(False))

    def _on_generate_clicked(self, btn: Gtk.Button) -> None:
        app = btn._wizard_app
        try:
            msg = run_wizard(app)
            self._show_status(msg)
            btn.set_sensitive(False)
            btn.set_label("Done")
            if self.on_rescan_cb is not None:
                self.on_rescan_cb()
        except Exception as e:
            self._show_status(f"Error generating config: {e}")

    def present(self) -> None:
        _present_dialog(self.dialog, self.parent_window)


# ── DiffViewerDialog ─────────────────────────────────────────────────


class DiffViewerDialog:
    """Show a unified diff with syntax highlighting."""

    def __init__(self, parent_window, title: str, diff_text: str) -> None:
        self.parent_window = parent_window
        self.diff_text = diff_text

        self.dialog = _make_dialog(title, width=750, height=600)

        self._build_ui()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()

        # Header
        header = Adw.HeaderBar()
        header.set_show_title(True)

        # Copy button
        copy_btn = Gtk.Button(
            icon_name="edit-copy-symbolic", tooltip_text="Copy diff to clipboard"
        )
        copy_btn.connect("clicked", self._on_copy)
        header.pack_start(copy_btn)

        toolbar_view.add_top_bar(header)

        # Stats bar
        adds, dels = diff_stats(self.diff_text)
        stats_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=12
        )
        stats_bar.set_margin_start(16)
        stats_bar.set_margin_end(16)
        stats_bar.set_margin_top(6)
        stats_bar.set_margin_bottom(6)

        if adds > 0:
            adds_label = Gtk.Label(label=f"+{adds}")
            adds_label.add_css_class("success")
            stats_bar.append(adds_label)

        if dels > 0:
            dels_label = Gtk.Label(label=f"-{dels}")
            dels_label.add_css_class("error")
            stats_bar.append(dels_label)

        if adds == 0 and dels == 0:
            no_changes = Gtk.Label(label="No changes")
            no_changes.add_css_class("dim-label")
            stats_bar.append(no_changes)

        total_label = Gtk.Label(
            label=f"{len(self.diff_text.splitlines())} lines"
        )
        total_label.add_css_class("dim-label")
        total_label.set_hexpand(True)
        total_label.set_halign(Gtk.Align.END)
        stats_bar.append(total_label)

        toolbar_view.add_top_bar(stats_bar)

        # Diff text view
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)

        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_monospace(True)
        self.text_view.set_wrap_mode(Gtk.WrapMode.NONE)
        self.text_view.set_left_margin(16)
        self.text_view.set_right_margin(16)
        self.text_view.set_top_margin(12)
        self.text_view.set_bottom_margin(12)

        buf = self.text_view.get_buffer()

        # Create tags for diff highlighting
        tag_table = buf.get_tag_table()

        add_tag = Gtk.TextTag(name="addition")
        add_tag.set_property("foreground", "#a6e3a1")
        tag_table.add(add_tag)

        del_tag = Gtk.TextTag(name="deletion")
        del_tag.set_property("foreground", "#f38ba8")
        tag_table.add(del_tag)

        ctx_tag = Gtk.TextTag(name="context")
        ctx_tag.set_property("foreground", "#8b949e")
        tag_table.add(ctx_tag)

        hdr_tag = Gtk.TextTag(name="header")
        hdr_tag.set_property("foreground", "#89b4fa")
        hdr_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(hdr_tag)

        hunk_tag = Gtk.TextTag(name="hunk")
        hunk_tag.set_property("foreground", "#d2a8ff")
        tag_table.add(hunk_tag)

        # Insert diff text with highlighting
        buf.set_text(self.diff_text)
        self._apply_diff_highlighting(buf)

        scrolled.set_child(self.text_view)
        toolbar_view.set_content(scrolled)

        if isinstance(self.dialog, Adw.Dialog):
            self.dialog.set_child(toolbar_view)
        else:
            self.dialog.set_content(toolbar_view)

    def _apply_diff_highlighting(self, buf: Gtk.TextBuffer) -> None:
        """Apply syntax highlighting to the diff content."""
        lines = self.diff_text.splitlines(keepends=True)
        offset = 0

        for line in lines:
            start_iter = buf.get_iter_at_offset(offset)
            end_iter = buf.get_iter_at_offset(offset + len(line))

            if line.startswith("+++") or line.startswith("---"):
                buf.apply_tag_by_name("header", start_iter, end_iter)
            elif line.startswith("@@"):
                buf.apply_tag_by_name("hunk", start_iter, end_iter)
            elif line.startswith("+"):
                buf.apply_tag_by_name("addition", start_iter, end_iter)
            elif line.startswith("-"):
                buf.apply_tag_by_name("deletion", start_iter, end_iter)
            else:
                buf.apply_tag_by_name("context", start_iter, end_iter)

            offset += len(line)

    def _on_copy(self, btn: Gtk.Button) -> None:
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(self.diff_text)
        btn.set_icon_name("emblem-ok-symbolic")
        GLib.timeout_add(
            1500, lambda: btn.set_icon_name("edit-copy-symbolic")
        )

    def present(self) -> None:
        _present_dialog(self.dialog, self.parent_window)


# ── BackupHistoryDialog ──────────────────────────────────────────────


class BackupHistoryDialog:
    """Show backup history for a dotfile with restore and diff options."""

    def __init__(
        self, parent_window, file_path: str, entry_name: str
    ) -> None:
        self.parent_window = parent_window
        self.file_path = file_path
        self.entry_name = entry_name

        self.dialog = _make_dialog(
            f"Backup History - {entry_name}", width=700, height=500
        )

        self._build_ui()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()

        # Header
        header = Adw.HeaderBar()
        header.set_show_title(True)
        toolbar_view.add_top_bar(header)

        # File path info bar
        path_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=8
        )
        path_bar.set_margin_start(16)
        path_bar.set_margin_end(16)
        path_bar.set_margin_top(4)
        path_bar.set_margin_bottom(4)
        path_bar.add_css_class("toolbar")

        path_icon = Gtk.Image.new_from_icon_name("folder-symbolic")
        path_bar.append(path_icon)

        path_label = Gtk.Label(label=self.file_path)
        path_label.set_halign(Gtk.Align.START)
        path_label.set_hexpand(True)
        path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        path_label.set_selectable(True)
        path_label.add_css_class("monospace")
        path_bar.append(path_label)

        toolbar_view.add_top_bar(path_bar)

        # Main scrollable content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12
        )
        self._content_box.set_margin_start(16)
        self._content_box.set_margin_end(16)
        self._content_box.set_margin_top(12)
        self._content_box.set_margin_bottom(12)

        # Status label
        self._status_label = Gtk.Label(label="")
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.add_css_class("dim-label")
        self._status_label.set_visible(False)
        self._status_label.set_wrap(True)
        self._content_box.append(self._status_label)

        # Backups list
        self._backups_group = Adw.PreferencesGroup()
        self._content_box.append(self._backups_group)

        scrolled.set_child(self._content_box)
        toolbar_view.set_content(scrolled)

        if isinstance(self.dialog, Adw.Dialog):
            self.dialog.set_child(toolbar_view)
        else:
            self.dialog.set_content(toolbar_view)

        self._refresh_backups()

    def _refresh_backups(self) -> None:
        """Load and display the backup list."""
        parent = self._backups_group.get_parent()
        if parent is not None:
            parent.remove(self._backups_group)

        self._backups_group = Adw.PreferencesGroup()
        self._backups_group.set_title("Backups")

        backups = get_backups(self.file_path)

        if not backups:
            self._backups_group.set_description("No backups found for this file")
        else:
            self._backups_group.set_description(
                f"{len(backups)} backup(s) available"
            )

            for backup in backups:
                row = Adw.ActionRow()
                row.set_title(backup.display_time)
                row.set_subtitle(
                    f"{_format_size(backup.size)} | {backup.reason} | "
                    f"{backup.relative_age}"
                )

                # View Diff button
                diff_btn = Gtk.Button(label="View Diff")
                diff_btn.add_css_class("flat")
                diff_btn.set_valign(Gtk.Align.CENTER)
                diff_btn._backup = backup
                diff_btn.connect("clicked", self._on_view_diff_clicked)
                row.add_suffix(diff_btn)

                # Restore button
                restore_btn = Gtk.Button(label="Restore")
                restore_btn.add_css_class("flat")
                restore_btn.add_css_class("destructive-action")
                restore_btn.set_valign(Gtk.Align.CENTER)
                restore_btn._backup = backup
                restore_btn.connect("clicked", self._on_restore_clicked)
                row.add_suffix(restore_btn)

                self._backups_group.add(row)

        self._content_box.append(self._backups_group)

    def _show_status(self, message: str) -> None:
        self._status_label.set_label(message)
        self._status_label.set_visible(True)
        GLib.timeout_add(5000, lambda: self._status_label.set_visible(False))

    def _on_view_diff_clicked(self, btn: Gtk.Button) -> None:
        backup = btn._backup
        diff_text = get_diff(self.file_path, backup)

        if not diff_text:
            self._show_status("No differences found (files are identical)")
            return

        diff_dialog = DiffViewerDialog(
            self.parent_window,
            f"Diff: {self.entry_name} ({backup.display_time} vs current)",
            diff_text,
        )
        diff_dialog.present()

    def _on_restore_clicked(self, btn: Gtk.Button) -> None:
        backup = btn._backup

        # Confirm restore
        confirm_dialog = Adw.AlertDialog()
        confirm_dialog.set_heading("Restore Backup?")
        confirm_dialog.set_body(
            f"Restore {self.entry_name} from backup dated "
            f"{backup.display_time}?\n\n"
            f"The current file will be backed up before restoring."
        )
        confirm_dialog.add_response("cancel", "Cancel")
        confirm_dialog.add_response("restore", "Restore")
        confirm_dialog.set_response_appearance(
            "restore", Adw.ResponseAppearance.DESTRUCTIVE
        )
        confirm_dialog.set_default_response("cancel")
        confirm_dialog.set_close_response("cancel")

        confirm_dialog.connect(
            "response", self._on_restore_response, backup
        )

        if isinstance(self.dialog, Adw.Dialog):
            confirm_dialog.present(self.dialog)
        else:
            confirm_dialog.present(self.dialog)

    def _on_restore_response(
        self, dialog, response: str, backup: BackupEntry
    ) -> None:
        if response != "restore":
            return

        success = restore_backup(backup)
        if success:
            self._show_status(
                f"Restored from backup ({backup.display_time})"
            )
            self._refresh_backups()
        else:
            self._show_status("Failed to restore backup")

    def present(self) -> None:
        _present_dialog(self.dialog, self.parent_window)
