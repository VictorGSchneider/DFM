"""Main application window - orchestrates all UI modules."""

import os

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from dfm.core.scanner import scan_dotfiles, DotfileEntry
from dfm.core.monitor import DotfileMonitor
from dfm.ui.window_sidebar import SidebarManager
from dfm.ui.window_all_dotfiles import AllDotfilesPage
from dfm.ui.window_config_page import ConfigPageBuilder
from dfm.ui.window_sync import SyncSection
from dfm.ui.window_dialogs import (
    ProfilesDialog, TemplatesDialog, WizardDialog,
)
from dfm.ui.window_analyzer import AnalyzerPage
from dfm.ui.window_io import ImportExportHelper, GistSharer


class DfmWindow(Adw.ApplicationWindow):
    """Main window - thin orchestrator wiring all modules together."""

    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="DFM - Dotfile Manager")
        self.set_default_size(1000, 700)

        self.dotfiles: list[DotfileEntry] = []
        self.current_entry: DotfileEntry | None = None

        self._monitor = DotfileMonitor(poll_interval=3.0)
        self._monitor.on_change(self._on_file_changed_external)

        self._sidebar = SidebarManager(
            on_entry_selected=self._on_entry_selected,
            on_analyzer_selected=self._on_analyzer_selected,
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
        self._analyzer_page = AnalyzerPage(
            on_navigate_to_entry=self._on_entry_selected,
        )
        self._io = ImportExportHelper(self)
        self._gist_sharer = GistSharer(self)

        self._build_ui()
        self._scan_and_populate()
        self._monitor.start()

    def destroy(self) -> None:
        self._monitor.stop()
        super().destroy()

    # ── UI Construction ─────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the main UI layout."""
        header = self._build_header()
        self._register_actions()

        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_shrink_start_child(False)
        self.paned.set_shrink_end_child(False)
        self.paned.set_position(270)

        self.paned.set_start_child(self._sidebar.build())

        self._toast_overlay = Adw.ToastOverlay()
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(
            Gtk.StackTransitionType.CROSSFADE
        )
        self._toast_overlay.set_child(self.content_stack)
        self.paned.set_end_child(self._toast_overlay)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(header)
        main_box.append(self.paned)
        self.set_content(main_box)

    def _build_header(self) -> Adw.HeaderBar:
        header = Adw.HeaderBar()
        header.set_show_title(True)
        header.set_title_widget(Adw.WindowTitle(
            title="DFM", subtitle="Dotfile Manager",
        ))

        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(self._build_menu())
        header.pack_end(menu_button)

        import_btn = Gtk.Button(icon_name="document-open-symbolic",
                                tooltip_text="Import Dotfiles")
        import_btn.connect("clicked", self._io.on_import_clicked)
        header.pack_start(import_btn)

        export_btn = Gtk.Button(icon_name="document-save-symbolic",
                                tooltip_text="Export Selected Dotfiles")
        export_btn.connect("clicked", self._io.on_export_clicked)
        header.pack_start(export_btn)

        sync_btn = Gtk.Button(icon_name="emblem-synchronizing-symbolic",
                              tooltip_text="Push Dotfiles to GitHub")
        sync_btn.connect("clicked", self._on_push_clicked)
        header.pack_start(sync_btn)

        return header

    def _build_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        menu.append("Rescan Dotfiles", "win.rescan")

        tools_section = Gio.Menu()
        tools_section.append("Analyzer & Debugger", "win.analyzer")
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
        return menu

    def _register_actions(self) -> None:
        """Register window actions."""
        actions = {
            "rescan": lambda *_: self._scan_and_populate(),
            "analyzer": lambda *_: self._on_analyzer_selected(),
            "import": lambda *_: self._io.on_import_clicked(None),
            "export-all": lambda *_: self._io.on_export_clicked(None),
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

        while True:
            child = self.content_stack.get_first_child()
            if child is None:
                break
            self.content_stack.remove(child)

        all_page = self._build_all_dotfiles_combined()
        self.content_stack.add_named(all_page, "all-dotfiles")

        analyzer_widget = self._analyzer_page.build(self.dotfiles)
        self.content_stack.add_named(analyzer_widget, "analyzer")

        seen_names: set[str] = set()
        for entry in self.dotfiles:
            page = self._config_builder.build(entry)
            stack_name = entry.name
            if stack_name in seen_names:
                stack_name = f"{entry.name}_{id(entry)}"
            seen_names.add(stack_name)
            entry._stack_name = stack_name
            self.content_stack.add_named(page, stack_name)

        self._sidebar.populate(self.dotfiles)
        self._monitor.track_entries(self.dotfiles)

    def _build_all_dotfiles_combined(self) -> Gtk.Widget:
        """Build the All Dotfiles page with sync section embedded."""
        all_widget = self._all_dotfiles_page.build(self.dotfiles)

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

    def _on_analyzer_selected(self) -> None:
        """Show the analyzer page."""
        self.content_stack.set_visible_child_name("analyzer")
        self.current_entry = None

    def _on_dotfile_toggled(self, entry: DotfileEntry, new_state: bool) -> None:
        """Handle dotfile toggle from All Dotfiles page."""
        entry.enabled = new_state

    # ── File Monitor ────────────────────────────────────────────────

    def _on_file_changed_external(self, file_path: str, change_type: str) -> None:
        """Handle external file change (called from monitor thread)."""
        GLib.idle_add(self._show_file_change_toast, file_path, change_type)

    def _show_file_change_toast(self, file_path: str, change_type: str) -> bool:
        basename = os.path.basename(file_path)
        toast = Adw.Toast.new(f"{basename} was {change_type} externally")
        toast.set_timeout(5)
        toast.set_button_label("Reload")
        toast.connect("button-clicked", lambda _: self._scan_and_populate())
        self._toast_overlay.add_toast(toast)
        return False

    # ── Tool dialogs ────────────────────────────────────────────────

    def _on_profiles(self) -> None:
        ProfilesDialog(self, self.dotfiles).present()

    def _on_templates(self) -> None:
        TemplatesDialog(self, on_rescan_cb=self._scan_and_populate).present()

    def _on_wizard(self) -> None:
        WizardDialog(
            self, self.dotfiles, on_rescan_cb=self._scan_and_populate,
        ).present()

    # ── GitHub Push/Pull (quick access) ─────────────────────────────

    def _on_push_clicked(self, _btn) -> None:
        self._sync_section._on_push_clicked(
            Gtk.Button() if _btn is None else _btn
        )

    def _on_pull_clicked(self, _btn) -> None:
        self._sync_section._on_pull_clicked(
            Gtk.Button() if _btn is None else _btn
        )

    # ── Gist sharing (from config page) ─────────────────────────────

    def share_as_gist(self, entry: DotfileEntry) -> None:
        """Upload a dotfile as a GitHub Gist."""
        self._gist_sharer.share(entry)

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
