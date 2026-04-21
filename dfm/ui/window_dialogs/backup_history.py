"""Show backup history for a dotfile with restore and diff options."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Pango

from dfm.core.backup import get_backups, restore_backup, get_diff, BackupEntry
from dfm.ui.window_dialogs._common import (
    format_size, make_dialog, present_dialog,
    set_dialog_content, StatusMixin,
)
from dfm.ui.window_dialogs.diff_viewer import DiffViewerDialog


class BackupHistoryDialog(StatusMixin):
    """Show backup history for a dotfile with restore and diff options."""

    def __init__(self, parent_window, file_path: str, entry_name: str) -> None:
        self.parent_window = parent_window
        self.file_path = file_path
        self.entry_name = entry_name
        self.dialog = make_dialog(
            f"Backup History - {entry_name}", width=700, height=500,
        )
        self._build_ui()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_title(True)
        toolbar_view.add_top_bar(header)

        toolbar_view.add_top_bar(self._build_path_bar())

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._content_box.set_margin_start(16)
        self._content_box.set_margin_end(16)
        self._content_box.set_margin_top(12)
        self._content_box.set_margin_bottom(12)

        self._status_label = Gtk.Label(label="")
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.add_css_class("dim-label")
        self._status_label.set_visible(False)
        self._status_label.set_wrap(True)
        self._content_box.append(self._status_label)

        self._backups_group = Adw.PreferencesGroup()
        self._content_box.append(self._backups_group)

        scrolled.set_child(self._content_box)
        toolbar_view.set_content(scrolled)
        set_dialog_content(self.dialog, toolbar_view)

        self._refresh_backups()

    def _build_path_bar(self) -> Gtk.Box:
        path_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        path_bar.set_margin_start(16)
        path_bar.set_margin_end(16)
        path_bar.set_margin_top(4)
        path_bar.set_margin_bottom(4)
        path_bar.add_css_class("toolbar")

        path_bar.append(Gtk.Image.new_from_icon_name("folder-symbolic"))

        path_label = Gtk.Label(label=self.file_path)
        path_label.set_halign(Gtk.Align.START)
        path_label.set_hexpand(True)
        path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        path_label.set_selectable(True)
        path_label.add_css_class("monospace")
        path_bar.append(path_label)
        return path_bar

    def _refresh_backups(self) -> None:
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
                self._backups_group.add(self._build_backup_row(backup))

        self._content_box.append(self._backups_group)

    def _build_backup_row(self, backup: BackupEntry) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_title(backup.display_time)
        row.set_subtitle(
            f"{format_size(backup.size)} | {backup.reason} | {backup.relative_age}"
        )

        diff_btn = Gtk.Button(label="View Diff")
        diff_btn.add_css_class("flat")
        diff_btn.set_valign(Gtk.Align.CENTER)
        diff_btn._backup = backup
        diff_btn.connect("clicked", self._on_view_diff_clicked)
        row.add_suffix(diff_btn)

        restore_btn = Gtk.Button(label="Restore")
        restore_btn.add_css_class("flat")
        restore_btn.add_css_class("destructive-action")
        restore_btn.set_valign(Gtk.Align.CENTER)
        restore_btn._backup = backup
        restore_btn.connect("clicked", self._on_restore_clicked)
        row.add_suffix(restore_btn)
        return row

    def _on_view_diff_clicked(self, btn: Gtk.Button) -> None:
        backup = btn._backup
        diff_text = get_diff(self.file_path, backup)
        if not diff_text:
            self._show_status("No differences found (files are identical)")
            return
        DiffViewerDialog(
            self.parent_window,
            f"Diff: {self.entry_name} ({backup.display_time} vs current)",
            diff_text,
        ).present()

    def _on_restore_clicked(self, btn: Gtk.Button) -> None:
        backup = btn._backup
        confirm = Adw.AlertDialog()
        confirm.set_heading("Restore Backup?")
        confirm.set_body(
            f"Restore {self.entry_name} from backup dated "
            f"{backup.display_time}?\n\n"
            f"The current file will be backed up before restoring."
        )
        confirm.add_response("cancel", "Cancel")
        confirm.add_response("restore", "Restore")
        confirm.set_response_appearance("restore", Adw.ResponseAppearance.DESTRUCTIVE)
        confirm.set_default_response("cancel")
        confirm.set_close_response("cancel")
        confirm.connect("response", self._on_restore_response, backup)
        confirm.present(self.dialog)

    def _on_restore_response(self, dialog, response: str, backup: BackupEntry) -> None:
        if response != "restore":
            return
        if restore_backup(backup):
            self._show_status(f"Restored from backup ({backup.display_time})")
            self._refresh_backups()
        else:
            self._show_status("Failed to restore backup")

    def present(self) -> None:
        present_dialog(self.dialog, self.parent_window)
