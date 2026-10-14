"""Import, export, and gist-sharing actions for the main window."""

import os
import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk

from dfm.core.distro import install_hint
from dfm.core.scanner import DotfileEntry
from dfm.core.exporter import export_dotfiles, import_dotfiles
from dfm.ui.tasks import run_async
from dfm.core.github_sync import (
    is_gh_available, is_gh_authenticated, upload_gist,
)


class ImportExportHelper:
    """Handles the archive import/export file dialogs for the main window."""

    def __init__(self, window) -> None:
        self.window = window

    def on_import_clicked(self, _btn) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Import Dotfiles Archive")

        file_filter = Gtk.FileFilter()
        file_filter.set_name("Dotfile Archives")
        file_filter.add_pattern("*.tar.gz")
        file_filter.add_pattern("*.tar.bz2")
        file_filter.add_pattern("*.tar.xz")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(file_filter)
        dialog.set_filters(filters)

        dialog.open(self.window, None, self._on_import_file_selected)

    def _on_import_file_selected(self, dialog, result) -> None:
        try:
            file = dialog.open_finish(result)
            if not file:
                return
            archive_path = file.get_path()
            confirm = Adw.AlertDialog()
            confirm.set_heading("Import Dotfiles")
            confirm.set_body(
                f"Import dotfiles from:\n{archive_path}\n\n"
                "Existing files will be backed up."
            )
            confirm.add_response("cancel", "Cancel")
            confirm.add_response("import", "Import")
            confirm.set_response_appearance(
                "import", Adw.ResponseAppearance.SUGGESTED
            )
            confirm.connect("response", self._on_import_confirmed, archive_path)
            confirm.present(self.window)
        except GLib.Error as e:
            if e.code != 2:  # GTK_DIALOG_ERROR_DISMISSED
                print(f"DFM import dialog error: {e}", file=sys.stderr)

    def _on_import_confirmed(self, dialog, response, archive_path) -> None:
        if response != "import":
            return
        self._toast("Importing dotfiles…")
        run_async(lambda: import_dotfiles(archive_path), self._on_import_done)

    def _on_import_done(self, actions, error) -> None:
        if error is not None:
            if isinstance(error, ValueError):
                message = "That file isn't a dotfiles archive."
            else:
                message = f"The archive couldn't be imported: {error}"
            self.window._show_message("Import Failed", message)
            return
        done = sum(1 for a in actions if a["status"] == "done")
        errors = sum(1 for a in actions if a["status"].startswith("error"))
        self._toast(f"Imported {done} files ({errors} errors)")
        self.window._scan_and_populate()

    def _toast(self, message: str) -> None:
        self.window._toast_overlay.add_toast(Adw.Toast.new(message))

    def on_export_clicked(self, _btn) -> None:
        enabled = [e for e in self.window.dotfiles if e.enabled]
        if not enabled:
            self.window._show_message(
                "No Dotfiles Selected",
                "Enable at least one dotfile to export.",
            )
            return

        dialog = Gtk.FileDialog()
        dialog.set_title("Export Dotfiles")
        dialog.set_initial_name("dotfiles_export.tar.gz")
        dialog.save(self.window, None, self._on_export_save_finish, enabled)

    def _on_export_save_finish(self, dialog, result, entries) -> None:
        try:
            file = dialog.save_finish(result)
            if not file:
                return
            # Honour the file name the user typed, not just its folder
            directory, name = os.path.split(file.get_path())
            self._toast("Exporting dotfiles…")
            run_async(
                lambda: export_dotfiles(entries, directory, archive_name=name),
                self._on_export_done,
            )
        except GLib.Error as e:
            if e.code != 2:
                print(f"DFM export dialog error: {e}", file=sys.stderr)


    def _on_export_done(self, archive, error) -> None:
        if error is not None:
            self.window._show_message("Export Failed", f"Couldn't create the archive: {error}")
            return
        self._toast(f"Exported to {archive}")


class GistSharer:
    """Handles gist-sharing UI for a single dotfile."""

    def __init__(self, window) -> None:
        self.window = window

    def share(self, entry: DotfileEntry) -> None:
        if not is_gh_available():
            self.window._show_message(
                "GitHub CLI Not Found",
                f"Install gh CLI: {install_hint('github-cli')}",
            )
            return
        if not is_gh_authenticated():
            self.window._show_message(
                "Not Authenticated", "Run 'gh auth login' first.",
            )
            return

        config_path = entry.get_config_path()
        if not config_path or not os.path.isfile(config_path):
            self.window._show_message(
                "File Not Found",
                f"Cannot share: {config_path or entry.path}",
            )
            return

        confirm = Adw.AlertDialog()
        confirm.set_heading("Share as Gist")
        confirm.set_body(
            f"Upload {os.path.basename(config_path)} as a GitHub Gist?\n\n"
            f"File: {config_path}"
        )
        confirm.add_response("cancel", "Cancel")
        confirm.add_response("secret", "Secret Gist")
        confirm.add_response("public", "Public Gist")
        confirm.set_response_appearance(
            "secret", Adw.ResponseAppearance.SUGGESTED
        )
        confirm.set_response_appearance(
            "public", Adw.ResponseAppearance.DESTRUCTIVE
        )
        confirm.connect("response", self._on_confirmed, entry, config_path)
        confirm.present(self.window)

    def _on_confirmed(self, dialog, response, entry, config_path) -> None:
        if response not in ("secret", "public"):
            return
        public = response == "public"
        desc = f"{entry.display_name} config (shared via DFM)"
        status = upload_gist(config_path, description=desc, public=public)
        if not status.success:
            self.window._show_message("Gist Failed", status.message)
            return

        toast = Adw.Toast.new(f"Gist created: {status.url}")
        toast.set_button_label("Copy URL")
        toast.connect(
            "button-clicked",
            lambda _: Gdk.Display.get_default().get_clipboard().set(status.url),
        )
        self.window._toast_overlay.add_toast(toast)
