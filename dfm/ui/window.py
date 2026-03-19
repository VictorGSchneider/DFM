"""Main application window - orchestrates all UI modules."""

import os
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk

from dfm.core.scanner import scan_dotfiles, DotfileEntry
from dfm.core.exporter import export_dotfiles, import_dotfiles
from dfm.core.monitor import DotfileMonitor
from dfm.ui.window_sidebar import SidebarManager
from dfm.ui.window_all_dotfiles import AllDotfilesPage
from dfm.ui.window_config_page import ConfigPageBuilder
from dfm.ui.window_sync import SyncSection
from dfm.ui.window_dialogs import (
    ProfilesDialog, TemplatesDialog, WizardDialog,
)
from dfm.core.github_sync import (
    is_gh_available, is_gh_authenticated,
    upload_gist, get_repo_path,
)


class DfmWindow(Adw.ApplicationWindow):
    """Main window - thin orchestrator wiring all modules together."""

    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="DFM - Dotfile Manager")
        self.set_default_size(1000, 700)

        self.dotfiles: list[DotfileEntry] = []
        self.current_entry: DotfileEntry | None = None

        # File monitor
        self._monitor = DotfileMonitor(poll_interval=3.0)
        self._monitor.on_change(self._on_file_changed_external)

        # Sub-modules
        self._sidebar = SidebarManager(
            on_entry_selected=self._on_entry_selected
        )
        self._all_dotfiles_page = AllDotfilesPage(
            on_dotfile_toggled_cb=self._on_dotfile_toggled,
            on_rescan_cb=self._scan_and_populate,
        )
        self._config_builder = ConfigPageBuilder(window=self)
        self._sync_section = SyncSection(
            window=self,
            get_dotfiles_cb=lambda: self.dotfiles,
            on_rescan_cb=self._scan_and_populate,
        )

        self._build_ui()
        self._scan_and_populate()
        self._monitor.start()

    def destroy(self) -> None:
        self._monitor.stop()
        super().destroy()

    # ── UI Construction ─────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the main UI layout."""
        # Header bar
        header = Adw.HeaderBar()
        header.set_show_title(True)
        header.set_title_widget(Adw.WindowTitle(
            title="DFM",
            subtitle="Dotfile Manager",
        ))

        # Menu
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu = Gio.Menu()
        menu.append("Rescan Dotfiles", "win.rescan")

        tools_section = Gio.Menu()
        tools_section.append("Profiles...", "win.profiles")
        tools_section.append("Templates...", "win.templates")
        tools_section.append("Dotfile Wizard...", "win.wizard")
        menu.append_section("Tools", tools_section)

        io_section = Gio.Menu()
        io_section.append("Import Dotfiles...", "win.import")
        io_section.append("Export All...", "win.export-all")
        menu.append_section("Import / Export", io_section)

        sync_section = Gio.Menu()
        sync_section.append("Push to GitHub", "win.push")
        sync_section.append("Pull from GitHub", "win.pull")
        menu.append_section("GitHub Sync", sync_section)

        menu.append("About", "win.about")
        menu_button.set_menu_model(menu)
        header.pack_end(menu_button)

        # Quick buttons in header
        import_btn = Gtk.Button(icon_name="document-open-symbolic",
                                tooltip_text="Import Dotfiles")
        import_btn.connect("clicked", self._on_import_clicked)
        header.pack_start(import_btn)

        export_btn = Gtk.Button(icon_name="document-save-symbolic",
                                tooltip_text="Export Selected Dotfiles")
        export_btn.connect("clicked", self._on_export_clicked)
        header.pack_start(export_btn)

        sync_btn = Gtk.Button(icon_name="emblem-synchronizing-symbolic",
                              tooltip_text="Push Dotfiles to GitHub")
        sync_btn.connect("clicked", self._on_push_clicked)
        header.pack_start(sync_btn)

        # Register actions
        self._register_actions()

        # Layout: sidebar + content
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_shrink_start_child(False)
        self.paned.set_shrink_end_child(False)
        self.paned.set_position(270)

        # Sidebar
        sidebar_widget = self._sidebar.build()
        self.paned.set_start_child(sidebar_widget)

        # Content area with toast overlay
        self._toast_overlay = Adw.ToastOverlay()
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(
            Gtk.StackTransitionType.CROSSFADE
        )
        self._toast_overlay.set_child(self.content_stack)
        self.paned.set_end_child(self._toast_overlay)

        # Assemble
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(header)
        main_box.append(self.paned)
        self.set_content(main_box)

    def _register_actions(self) -> None:
        """Register window actions."""
        actions = {
            "rescan": lambda *_: self._scan_and_populate(),
            "import": lambda *_: self._on_import_clicked(None),
            "export-all": lambda *_: self._on_export_clicked(None),
            "push": lambda *_: self._on_push_clicked(None),
            "pull": lambda *_: self._on_pull_clicked(None),
            "profiles": lambda *_: self._on_profiles(),
            "templates": lambda *_: self._on_templates(),
            "wizard": lambda *_: self._on_wizard(),
            "about": self._on_about,
        }
        for name, handler in actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)

    # ── Data Loading ────────────────────────────────────────────────

    def _scan_and_populate(self) -> None:
        """Scan for dotfiles and populate all UI."""
        self.dotfiles = scan_dotfiles()

        # Clear content stack
        while True:
            child = self.content_stack.get_first_child()
            if child is None:
                break
            self.content_stack.remove(child)

        # Build All Dotfiles page (includes sync section)
        all_page = self._build_all_dotfiles_combined()
        self.content_stack.add_named(all_page, "all-dotfiles")

        # Build each config page (use index suffix to avoid name collisions)
        seen_names: set[str] = set()
        for entry in self.dotfiles:
            page = self._config_builder.build(entry)
            stack_name = entry.name
            if stack_name in seen_names:
                stack_name = f"{entry.name}_{id(entry)}"
            seen_names.add(stack_name)
            entry._stack_name = stack_name
            self.content_stack.add_named(page, stack_name)

        # Populate sidebar
        self._sidebar.populate(self.dotfiles)

        # Track files in monitor
        self._monitor.track_entries(self.dotfiles)

    def _build_all_dotfiles_combined(self) -> Gtk.Widget:
        """Build the All Dotfiles page with sync section embedded."""
        # Build the all dotfiles page (returns an outer_box with scroll)
        all_widget = self._all_dotfiles_page.build(self.dotfiles)

        # Append sync section into the content_box inside the page
        content_box = self._all_dotfiles_page._content_box
        if content_box:
            sync_sep = Gtk.Separator()
            sync_sep.set_margin_top(16)
            content_box.append(sync_sep)
            sync_widget = self._sync_section.build()
            content_box.append(sync_widget)

        return all_widget

    # ── Navigation ──────────────────────────────────────────────────

    def _on_entry_selected(self, entry: DotfileEntry | None) -> None:
        """Handle sidebar selection."""
        if entry is None:
            self.content_stack.set_visible_child_name("all-dotfiles")
            self.current_entry = None
        else:
            stack_name = getattr(entry, '_stack_name', entry.name)
            self.content_stack.set_visible_child_name(stack_name)
            self.current_entry = entry

    def _on_dotfile_toggled(self, entry: DotfileEntry,
                            new_state: bool) -> None:
        """Handle dotfile toggle from All Dotfiles page."""
        entry.enabled = new_state

    # ── File Monitor ────────────────────────────────────────────────

    def _on_file_changed_external(self, file_path: str,
                                  change_type: str) -> None:
        """Handle external file change (called from monitor thread)."""
        GLib.idle_add(self._show_file_change_toast, file_path, change_type)

    def _show_file_change_toast(self, file_path: str,
                                change_type: str) -> bool:
        """Show a toast notification for external file changes."""
        basename = os.path.basename(file_path)
        toast = Adw.Toast.new(
            f"{basename} was {change_type} externally"
        )
        toast.set_timeout(5)
        toast.set_button_label("Reload")
        toast.connect("button-clicked",
                      lambda _: self._scan_and_populate())
        self._toast_overlay.add_toast(toast)
        return False  # Don't repeat

    # ── Tool dialogs ────────────────────────────────────────────────

    def _on_profiles(self) -> None:
        """Open profiles dialog."""
        dialog = ProfilesDialog(self, self.dotfiles)
        dialog.present()

    def _on_templates(self) -> None:
        """Open templates dialog."""
        dialog = TemplatesDialog(self, on_rescan_cb=self._scan_and_populate)
        dialog.present()

    def _on_wizard(self) -> None:
        """Open dotfile wizard dialog."""
        dialog = WizardDialog(
            self, self.dotfiles,
            on_rescan_cb=self._scan_and_populate,
        )
        dialog.present()

    # ── GitHub Push/Pull (quick access) ─────────────────────────────

    def _on_push_clicked(self, _btn) -> None:
        """Delegate to sync section."""
        self._sync_section._on_push_clicked(
            Gtk.Button() if _btn is None else _btn
        )

    def _on_pull_clicked(self, _btn) -> None:
        """Delegate to sync section."""
        self._sync_section._on_pull_clicked(
            Gtk.Button() if _btn is None else _btn
        )

    # ── Gist sharing (from config page) ─────────────────────────────

    def share_as_gist(self, entry: DotfileEntry) -> None:
        """Upload a dotfile as a GitHub Gist."""
        if not is_gh_available():
            self._show_message("GitHub CLI Not Found",
                               "Install gh CLI: sudo pacman -S github-cli")
            return
        if not is_gh_authenticated():
            self._show_message("Not Authenticated",
                               "Run 'gh auth login' first.")
            return

        config_path = entry.get_config_path()
        if not config_path or not os.path.isfile(config_path):
            self._show_message("File Not Found",
                               f"Cannot share: {config_path or entry.path}")
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
        confirm.connect("response", self._on_gist_confirmed,
                        entry, config_path)
        confirm.present(self)

    def _on_gist_confirmed(self, dialog, response, entry, config_path):
        if response in ("secret", "public"):
            public = response == "public"
            desc = f"{entry.display_name} config (shared via DFM)"
            status = upload_gist(config_path, description=desc,
                                 public=public)
            if status.success:
                toast = Adw.Toast.new(f"Gist created: {status.url}")
                toast.set_button_label("Copy URL")
                toast.connect("button-clicked",
                              lambda _: Gdk.Display.get_default()
                              .get_clipboard().set(status.url))
                self._toast_overlay.add_toast(toast)
            else:
                self._show_message("Gist Failed", status.message)

    # ── Import / Export ─────────────────────────────────────────────

    def _on_import_clicked(self, _btn) -> None:
        """Handle import button click."""
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

        dialog.open(self, None, self._on_import_file_selected)

    def _on_import_file_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            if file:
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
                confirm.connect("response", self._on_import_confirmed,
                                archive_path)
                confirm.present(self)
        except GLib.Error as e:
            # User cancelled the dialog — not an error
            if e.code != 2:  # 2 = GTK_DIALOG_ERROR_DISMISSED
                import sys
                print(f"DFM import dialog error: {e}", file=sys.stderr)

    def _on_import_confirmed(self, dialog, response, archive_path):
        if response == "import":
            actions = import_dotfiles(archive_path)
            done = sum(1 for a in actions if a["status"] == "done")
            errors = sum(1 for a in actions
                         if a["status"].startswith("error"))
            toast = Adw.Toast.new(
                f"Imported {done} files ({errors} errors)"
            )
            self._toast_overlay.add_toast(toast)
            self._scan_and_populate()

    def _on_export_clicked(self, _btn) -> None:
        """Handle export button click."""
        enabled = [e for e in self.dotfiles if e.enabled]
        if not enabled:
            self._show_message("No Dotfiles Selected",
                               "Enable at least one dotfile to export.")
            return

        dialog = Gtk.FileDialog()
        dialog.set_title("Export Dotfiles")
        dialog.set_initial_name("dotfiles_export.tar.gz")
        dialog.save(self, None, self._on_export_save_finish, enabled)

    def _on_export_save_finish(self, dialog, result, entries):
        try:
            file = dialog.save_finish(result)
            if file:
                output_path = file.get_path()
                if output_path.endswith(".tar.gz"):
                    output_dir = os.path.dirname(output_path)
                else:
                    output_dir = output_path
                archive = export_dotfiles(entries, output_dir)
                toast = Adw.Toast.new(f"Exported to {archive}")
                self._toast_overlay.add_toast(toast)
        except GLib.Error as e:
            if e.code != 2:
                import sys
                print(f"DFM export dialog error: {e}", file=sys.stderr)

    # ── Helpers ──────────────────────────────────────────────────────

    def _show_message(self, heading: str, body: str) -> None:
        """Show a simple alert dialog."""
        dialog = Adw.AlertDialog()
        dialog.set_heading(heading)
        dialog.set_body(body)
        dialog.add_response("ok", "OK")
        dialog.present(self)

    def _on_about(self, *_args) -> None:
        """Show the about dialog."""
        about = Adw.AboutDialog()
        about.set_application_name("DFM")
        about.set_version("2.0.0")
        about.set_developer_name("DFM Contributors")
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_comments(
            "A graphical dotfile manager for Arch Linux.\n"
            "Detect, configure, import/export, and sync your "
            "dotfiles with GitHub."
        )
        about.set_application_icon("preferences-other")
        about.present(self)
