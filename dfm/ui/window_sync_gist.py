"""Gist import handler for the GitHub sync section."""

import os
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from dfm.core.github_sync import (
    is_gh_available, is_gh_authenticated, import_gist,
)


def on_import_gist_clicked(section, _btn: Gtk.Button) -> None:
    """Show the import-from-gist dialog."""
    if not is_gh_available():
        section._show_gh_missing_dialog()
        return
    if not is_gh_authenticated():
        section._show_gh_auth_dialog()
        return

    dialog = Adw.AlertDialog()
    dialog.set_heading("Import from Gist")
    dialog.set_body("Enter a Gist ID or URL and the local path to save to.")

    content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    content_box.set_margin_top(12)
    content_box.set_margin_bottom(4)
    content_box.set_margin_start(12)
    content_box.set_margin_end(12)

    gist_entry = Adw.EntryRow()
    gist_entry.set_title("Gist ID or URL")
    gist_group = Adw.PreferencesGroup()
    gist_group.add(gist_entry)
    content_box.append(gist_group)

    target_entry = Adw.EntryRow()
    target_entry.set_title("Save to path")
    target_entry.set_text(os.path.join(str(Path.home()), ".config", ""))
    target_group = Adw.PreferencesGroup()
    target_group.add(target_entry)
    content_box.append(target_group)

    dialog.set_extra_child(content_box)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("import", "Import")
    dialog.set_response_appearance("import", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("cancel")
    dialog.set_close_response("cancel")
    dialog.connect(
        "response", _on_import_gist_response,
        section, gist_entry, target_entry,
    )
    dialog.present(section._window)


def _on_import_gist_response(dialog: Adw.AlertDialog, response: str,
                             section,
                             gist_entry: Adw.EntryRow,
                             target_entry: Adw.EntryRow) -> None:
    if response != "import":
        return

    gist_id = gist_entry.get_text().strip()
    target_path = target_entry.get_text().strip()

    if not gist_id:
        section._alert("Missing Gist ID", "Please enter a Gist ID or URL.")
        return
    if not target_path:
        section._alert("Missing Target Path",
                       "Please enter a path to save the file.")
        return

    status = import_gist(gist_id, target_path)
    heading = "Import Complete" if status.success else "Import Failed"
    section._alert(heading, status.message)

    if status.success and section._on_rescan:
        section._on_rescan()
