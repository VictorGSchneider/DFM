"""Main application window - GNOME Settings-inspired dotfile manager."""

import os
import json
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk, Pango

from dfm.scanner import scan_dotfiles, DotfileEntry
from dfm.parser import (
    parse_config, ConfigField, FieldType, ParsedConfig,
    update_config_value, BOOL_TRUE, BOOL_FALSE,
)
from dfm.exporter import export_dotfiles, import_dotfiles
from dfm.viewer import TextViewerDialog
from dfm.github_sync import (
    is_gh_available, is_gh_authenticated, get_gh_username,
    upload_gist, init_repo, clone_repo, push_dotfiles,
    pull_dotfiles, get_repo_status, get_repo_path, save_repo_path,
)


class DfmWindow(Adw.ApplicationWindow):
    """Main window with sidebar navigation and config panel."""

    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="DFM - Dotfile Manager")
        self.set_default_size(1000, 700)

        self.dotfiles: list[DotfileEntry] = []
        self.current_entry: DotfileEntry | None = None
        self.current_config: ParsedConfig | None = None

        self._build_ui()
        self._scan_and_populate()

    # ── UI Construction ─────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the main UI layout."""
        # Header bar with menu
        header = Adw.HeaderBar()
        header.set_show_title(True)
        header.set_title_widget(Adw.WindowTitle(
            title="DFM",
            subtitle="Dotfile Manager",
        ))

        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu = Gio.Menu()
        menu.append("Rescan Dotfiles", "win.rescan")
        menu.append("Import Dotfiles...", "win.import")
        menu.append("Export All...", "win.export-all")
        sync_section = Gio.Menu()
        sync_section.append("Push to GitHub", "win.push")
        sync_section.append("Pull from GitHub", "win.pull")
        menu.append_section("GitHub Sync", sync_section)
        menu.append("About", "win.about")
        menu_button.set_menu_model(menu)
        header.pack_end(menu_button)

        # Import/Export buttons in header
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

        # Actions
        rescan_action = Gio.SimpleAction.new("rescan", None)
        rescan_action.connect("activate", lambda *_: self._scan_and_populate())
        self.add_action(rescan_action)

        import_action = Gio.SimpleAction.new("import", None)
        import_action.connect("activate", lambda *_: self._on_import_clicked(None))
        self.add_action(import_action)

        export_action = Gio.SimpleAction.new("export-all", None)
        export_action.connect("activate", lambda *_: self._on_export_clicked(None))
        self.add_action(export_action)

        push_action = Gio.SimpleAction.new("push", None)
        push_action.connect("activate", lambda *_: self._on_push_clicked(None))
        self.add_action(push_action)

        pull_action = Gio.SimpleAction.new("pull", None)
        pull_action.connect("activate", lambda *_: self._on_pull_clicked(None))
        self.add_action(pull_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        # Main layout: sidebar + content
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_shrink_start_child(False)
        self.paned.set_shrink_end_child(False)
        self.paned.set_position(260)

        # Sidebar
        self._build_sidebar()
        self.paned.set_start_child(self.sidebar_box)

        # Content area
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(
            Gtk.StackTransitionType.CROSSFADE
        )

        content_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_frame.append(self.content_stack)
        self.paned.set_end_child(content_frame)

        # Assemble
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(header)
        main_box.append(self.paned)
        self.set_content(main_box)

    def _build_sidebar(self) -> None:
        """Build the sidebar with dotfile list."""
        self.sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.sidebar_box.add_css_class("sidebar")
        self.sidebar_box.set_size_request(260, -1)

        # Sidebar scrolled area
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.sidebar_list = Gtk.ListBox()
        self.sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sidebar_list.add_css_class("navigation-sidebar")
        self.sidebar_list.connect("row-selected", self._on_sidebar_select)

        scrolled.set_child(self.sidebar_list)
        self.sidebar_box.append(scrolled)

    # ── Data Loading ────────────────────────────────────────────────

    def _scan_and_populate(self) -> None:
        """Scan for dotfiles and populate the sidebar."""
        self.dotfiles = scan_dotfiles()

        # Clear sidebar
        while True:
            row = self.sidebar_list.get_row_at_index(0)
            if row is None:
                break
            self.sidebar_list.remove(row)

        # Clear content stack
        while True:
            child = self.content_stack.get_first_child()
            if child is None:
                break
            self.content_stack.remove(child)

        # Add "All Dotfiles" row
        all_row = self._make_sidebar_row(
            "starred-symbolic", "All Dotfiles", None
        )
        all_row._dfm_entry = None
        self.sidebar_list.append(all_row)

        # Build the All Dotfiles page
        all_page = self._build_all_dotfiles_page()
        self.content_stack.add_named(all_page, "all-dotfiles")

        # Add each dotfile
        for entry in self.dotfiles:
            row = self._make_sidebar_row(
                entry.icon_name, entry.display_name, entry
            )
            row._dfm_entry = entry
            self.sidebar_list.append(row)

            # Build config page
            page = self._build_config_page(entry)
            self.content_stack.add_named(page, entry.name)

        # Select first row
        first = self.sidebar_list.get_row_at_index(0)
        if first:
            self.sidebar_list.select_row(first)

    def _make_sidebar_row(self, icon_name: str, label: str,
                          entry: DotfileEntry | None) -> Gtk.ListBoxRow:
        """Create a sidebar row."""
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(20)
        box.append(icon)

        lbl = Gtk.Label(label=label)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(True)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(lbl)

        row.set_child(box)
        return row

    # ── All Dotfiles Page ───────────────────────────────────────────

    def _build_all_dotfiles_page(self) -> Gtk.Widget:
        """Build the overview page with toggles for all dotfiles."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(700)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        # Title
        title = Gtk.Label(label="All Dotfiles")
        title.add_css_class("title-1")
        title.set_halign(Gtk.Align.START)
        box.append(title)

        subtitle = Gtk.Label(
            label=f"{len(self.dotfiles)} dotfiles detected on this system"
        )
        subtitle.add_css_class("dim-label")
        subtitle.set_halign(Gtk.Align.START)
        subtitle.set_margin_bottom(16)
        box.append(subtitle)

        # Group by category
        groups: dict[str, list[DotfileEntry]] = {}
        for entry in self.dotfiles:
            cat = _categorize(entry)
            groups.setdefault(cat, []).append(entry)

        for group_name, entries in sorted(groups.items()):
            group = Adw.PreferencesGroup()
            group.set_title(group_name)

            for entry in entries:
                row = Adw.SwitchRow()
                row.set_title(entry.display_name)
                config_path = entry.get_config_path()
                row.set_subtitle(
                    os.path.relpath(config_path, str(Path.home()))
                    if config_path else entry.path
                )
                row.set_active(entry.enabled)
                row.connect("notify::active",
                            self._on_dotfile_toggled, entry)
                group.add(row)

            box.append(group)

        # ── GitHub Sync Section ──
        sync_separator = Gtk.Separator()
        sync_separator.set_margin_top(16)
        box.append(sync_separator)

        sync_title = Gtk.Label(label="GitHub Sync")
        sync_title.add_css_class("title-1")
        sync_title.set_halign(Gtk.Align.START)
        sync_title.set_margin_top(16)
        box.append(sync_title)

        sync_desc = Gtk.Label(
            label="Sync your dotfiles with a GitHub repository. "
                  "Uses the standard dotfiles repo approach with full "
                  "directory structure, commit history, and bidirectional sync."
        )
        sync_desc.add_css_class("dim-label")
        sync_desc.set_halign(Gtk.Align.START)
        sync_desc.set_wrap(True)
        sync_desc.set_margin_bottom(12)
        box.append(sync_desc)

        # Status group
        self.sync_status_group = Adw.PreferencesGroup()
        self.sync_status_group.set_title("Status")
        self._refresh_sync_status_group()
        box.append(self.sync_status_group)

        # Actions group
        sync_actions_group = Adw.PreferencesGroup()
        sync_actions_group.set_title("Actions")

        # Push button
        push_row = Adw.ActionRow()
        push_row.set_title("Push to GitHub")
        push_row.set_subtitle(
            "Copy enabled dotfiles to the repo, commit, and push"
        )
        push_btn = Gtk.Button(label="Push")
        push_btn.add_css_class("suggested-action")
        push_btn.set_valign(Gtk.Align.CENTER)
        push_btn.connect("clicked", self._on_push_clicked)
        push_row.add_suffix(push_btn)
        push_row.set_activatable_widget(push_btn)
        sync_actions_group.add(push_row)

        # Pull button
        pull_row = Adw.ActionRow()
        pull_row.set_title("Pull from GitHub")
        pull_row.set_subtitle(
            "Download dotfiles from repo and install to home"
        )
        pull_btn = Gtk.Button(label="Pull")
        pull_btn.add_css_class("flat")
        pull_btn.set_valign(Gtk.Align.CENTER)
        pull_btn.connect("clicked", self._on_pull_clicked)
        pull_row.add_suffix(pull_btn)
        pull_row.set_activatable_widget(pull_btn)
        sync_actions_group.add(pull_row)

        box.append(sync_actions_group)

        # Setup group
        setup_group = Adw.PreferencesGroup()
        setup_group.set_title("Setup")
        setup_group.set_description(
            "Requires GitHub CLI (gh). Install: sudo pacman -S github-cli"
        )

        # Init new repo
        init_row = Adw.ActionRow()
        init_row.set_title("Create New Dotfiles Repo")
        init_row.set_subtitle(
            "Create a new private repo on GitHub and clone it"
        )
        init_btn = Gtk.Button(label="Create")
        init_btn.add_css_class("flat")
        init_btn.set_valign(Gtk.Align.CENTER)
        init_btn.connect("clicked", self._on_init_repo_clicked)
        init_row.add_suffix(init_btn)
        init_row.set_activatable_widget(init_btn)
        setup_group.add(init_row)

        # Clone existing repo
        clone_row = Adw.ActionRow()
        clone_row.set_title("Clone Existing Repo")
        clone_row.set_subtitle(
            "Clone your existing dotfiles repo from GitHub"
        )
        clone_btn = Gtk.Button(label="Clone")
        clone_btn.add_css_class("flat")
        clone_btn.set_valign(Gtk.Align.CENTER)
        clone_btn.connect("clicked", self._on_clone_repo_clicked)
        clone_row.add_suffix(clone_btn)
        clone_row.set_activatable_widget(clone_btn)
        setup_group.add(clone_row)

        box.append(setup_group)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        return scrolled

    def _refresh_sync_status_group(self) -> None:
        """Update the sync status display."""
        # Clear existing rows
        while True:
            child = self.sync_status_group.get_first_child()
            if child is None:
                break
            # PreferencesGroup wraps children; use remove
            # Adw.PreferencesGroup doesn't have a simple clear, rebuild
            break

        status = get_repo_status()

        # gh CLI status
        gh_row = Adw.ActionRow()
        gh_row.set_title("GitHub CLI")
        if not status["gh_available"]:
            gh_row.set_subtitle("Not installed")
            icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            icon.add_css_class("warning")
        elif not status["gh_authenticated"]:
            gh_row.set_subtitle("Not authenticated — run 'gh auth login'")
            icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        else:
            gh_row.set_subtitle(f"Authenticated as {status['username']}")
            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        icon.set_valign(Gtk.Align.CENTER)
        gh_row.add_suffix(icon)
        self.sync_status_group.add(gh_row)

        # Repo status
        repo_row = Adw.ActionRow()
        repo_row.set_title("Dotfiles Repository")
        if status["configured"] and status["exists"]:
            sub_parts = []
            if status["remote_url"]:
                sub_parts.append(status["remote_url"])
            if status["branch"]:
                sub_parts.append(f"branch: {status['branch']}")
            if status["last_commit"]:
                sub_parts.append(status["last_commit"])
            repo_row.set_subtitle(" · ".join(sub_parts) or status["path"])
            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        elif status["configured"]:
            repo_row.set_subtitle(f"Configured but not found: {status['path']}")
            icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        else:
            repo_row.set_subtitle("Not configured — create or clone a repo")
            icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
        icon.set_valign(Gtk.Align.CENTER)
        repo_row.add_suffix(icon)
        self.sync_status_group.add(repo_row)

    def _on_push_clicked(self, _btn: Gtk.Button) -> None:
        """Handle push to GitHub."""
        if not is_gh_available():
            self._show_gh_missing_dialog()
            return
        if not is_gh_authenticated():
            self._show_gh_auth_dialog()
            return
        if not get_repo_path():
            info = Adw.AlertDialog()
            info.set_heading("No Repository")
            info.set_body(
                "Create or clone a dotfiles repo first using "
                "the Setup section below."
            )
            info.add_response("ok", "OK")
            info.present(self)
            return

        enabled = [e for e in self.dotfiles if e.enabled]
        if not enabled:
            info = Adw.AlertDialog()
            info.set_heading("No Dotfiles Selected")
            info.set_body("Enable at least one dotfile to push.")
            info.add_response("ok", "OK")
            info.present(self)
            return

        # Confirm
        confirm = Adw.AlertDialog()
        confirm.set_heading("Push Dotfiles to GitHub")
        confirm.set_body(
            f"Push {len(enabled)} enabled dotfiles to your GitHub repo?\n\n"
            "This will copy the files, commit, and push."
        )
        confirm.add_response("cancel", "Cancel")
        confirm.add_response("push", "Push")
        confirm.set_response_appearance(
            "push", Adw.ResponseAppearance.SUGGESTED
        )
        confirm.connect("response", self._on_push_confirmed, enabled)
        confirm.present(self)

    def _on_push_confirmed(self, dialog: Adw.AlertDialog,
                           response: str,
                           entries: list[DotfileEntry]) -> None:
        """Execute push."""
        if response != "push":
            return

        status = push_dotfiles(entries)
        info = Adw.AlertDialog()
        info.set_heading("Push " + ("Complete" if status.success else "Failed"))
        body = status.message
        if status.details:
            body += "\n\n" + "\n".join(status.details[:20])
            if len(status.details) > 20:
                body += f"\n... and {len(status.details) - 20} more"
        info.set_body(body)
        info.add_response("ok", "OK")
        info.present(self)

    def _on_pull_clicked(self, _btn: Gtk.Button) -> None:
        """Handle pull from GitHub."""
        if not is_gh_available():
            self._show_gh_missing_dialog()
            return
        if not is_gh_authenticated():
            self._show_gh_auth_dialog()
            return
        if not get_repo_path():
            info = Adw.AlertDialog()
            info.set_heading("No Repository")
            info.set_body(
                "Create or clone a dotfiles repo first."
            )
            info.add_response("ok", "OK")
            info.present(self)
            return

        confirm = Adw.AlertDialog()
        confirm.set_heading("Pull Dotfiles from GitHub")
        confirm.set_body(
            "Pull dotfiles from your GitHub repo?\n\n"
            "Existing files will be backed up with .dfm_backup extension."
        )
        confirm.add_response("cancel", "Cancel")
        confirm.add_response("pull", "Pull")
        confirm.set_response_appearance(
            "pull", Adw.ResponseAppearance.SUGGESTED
        )
        confirm.connect("response", self._on_pull_confirmed)
        confirm.present(self)

    def _on_pull_confirmed(self, dialog: Adw.AlertDialog,
                           response: str) -> None:
        """Execute pull."""
        if response != "pull":
            return

        status = pull_dotfiles()
        info = Adw.AlertDialog()
        info.set_heading("Pull " + ("Complete" if status.success else "Failed"))
        body = status.message
        if status.details:
            body += "\n\n" + "\n".join(status.details[:20])
        info.set_body(body)
        info.add_response("ok", "OK")
        info.present(self)

        if status.success:
            self._scan_and_populate()

    def _on_init_repo_clicked(self, _btn: Gtk.Button) -> None:
        """Handle create new repo."""
        if not is_gh_available():
            self._show_gh_missing_dialog()
            return
        if not is_gh_authenticated():
            self._show_gh_auth_dialog()
            return

        confirm = Adw.AlertDialog()
        confirm.set_heading("Create Dotfiles Repository")
        confirm.set_body(
            "Create a new private 'dotfiles' repo on GitHub?\n\n"
            "The repo will be cloned to ~/.dotfiles locally."
        )
        confirm.add_response("cancel", "Cancel")
        confirm.add_response("create", "Create")
        confirm.set_response_appearance(
            "create", Adw.ResponseAppearance.SUGGESTED
        )
        confirm.connect("response", self._on_init_confirmed)
        confirm.present(self)

    def _on_init_confirmed(self, dialog: Adw.AlertDialog,
                           response: str) -> None:
        """Execute repo init."""
        if response != "create":
            return

        status = init_repo()
        info = Adw.AlertDialog()
        info.set_heading(
            "Repo Created" if status.success else "Creation Failed"
        )
        body = status.message
        if status.url:
            body += f"\n\n{status.url}"
        info.set_body(body)
        info.add_response("ok", "OK")
        info.present(self)

    def _on_clone_repo_clicked(self, _btn: Gtk.Button) -> None:
        """Handle clone existing repo."""
        if not is_gh_available():
            self._show_gh_missing_dialog()
            return
        if not is_gh_authenticated():
            self._show_gh_auth_dialog()
            return

        confirm = Adw.AlertDialog()
        confirm.set_heading("Clone Dotfiles Repository")
        confirm.set_body(
            "Clone your existing 'dotfiles' repo from GitHub?\n\n"
            "It will be cloned to ~/.dotfiles locally."
        )
        confirm.add_response("cancel", "Cancel")
        confirm.add_response("clone", "Clone")
        confirm.set_response_appearance(
            "clone", Adw.ResponseAppearance.SUGGESTED
        )
        confirm.connect("response", self._on_clone_confirmed)
        confirm.present(self)

    def _on_clone_confirmed(self, dialog: Adw.AlertDialog,
                            response: str) -> None:
        """Execute clone."""
        if response != "clone":
            return

        status = clone_repo()
        info = Adw.AlertDialog()
        info.set_heading(
            "Clone Complete" if status.success else "Clone Failed"
        )
        body = status.message
        if status.url:
            body += f"\n\n{status.url}"
        info.set_body(body)
        info.add_response("ok", "OK")
        info.present(self)

    def _on_dotfile_toggled(self, switch_row: Adw.SwitchRow,
                            _pspec, entry: DotfileEntry) -> None:
        """Handle toggling a dotfile on/off."""
        entry.enabled = switch_row.get_active()

    # ── Config Page ─────────────────────────────────────────────────

    def _build_config_page(self, entry: DotfileEntry) -> Gtk.Widget:
        """Build the configuration page for a single dotfile."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(700)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        # Title
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_icon = Gtk.Image.new_from_icon_name(entry.icon_name)
        title_icon.set_pixel_size(32)
        title_box.append(title_icon)

        title_label = Gtk.Label(label=entry.display_name)
        title_label.add_css_class("title-1")
        title_label.set_halign(Gtk.Align.START)
        title_box.append(title_label)
        box.append(title_box)

        # Path subtitle
        config_path = entry.get_config_path()
        path_label = Gtk.Label(
            label=config_path if config_path else entry.path
        )
        path_label.add_css_class("dim-label")
        path_label.set_halign(Gtk.Align.START)
        path_label.set_margin_bottom(8)
        path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        path_label.set_selectable(True)
        box.append(path_label)

        # Action buttons row
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions_box.set_margin_bottom(16)

        open_btn = Gtk.Button(label="Open in Editor")
        open_btn.add_css_class("flat")
        open_btn.connect("clicked", self._on_open_editor, entry)
        actions_box.append(open_btn)

        open_dir_btn = Gtk.Button(label="Open Directory")
        open_dir_btn.add_css_class("flat")
        open_dir_btn.connect("clicked", self._on_open_directory, entry)
        actions_box.append(open_dir_btn)

        export_btn = Gtk.Button(label="Export")
        export_btn.add_css_class("flat")
        export_btn.connect("clicked", self._on_export_single, entry)
        actions_box.append(export_btn)

        # View raw text button
        view_raw_btn = Gtk.Button(label="View Raw")
        view_raw_btn.add_css_class("flat")
        view_raw_btn.connect("clicked", self._on_view_raw, entry)
        actions_box.append(view_raw_btn)

        # Share as Gist button
        gist_btn = Gtk.Button(label="Share as Gist")
        gist_btn.add_css_class("flat")
        gist_btn.connect("clicked", self._on_share_gist, entry)
        actions_box.append(gist_btn)

        box.append(actions_box)

        # Parse the config file
        if config_path and os.path.isfile(config_path):
            parsed = parse_config(config_path)
            self._populate_fields(box, parsed, entry)
        else:
            empty = Adw.StatusPage()
            empty.set_title("No Configuration File")
            empty.set_description(
                "This dotfile doesn't have a parseable config file."
            )
            empty.set_icon_name("dialog-information-symbolic")
            box.append(empty)

        clamp.set_child(box)
        scrolled.set_child(clamp)
        return scrolled

    def _populate_fields(self, container: Gtk.Box, parsed: ParsedConfig,
                         entry: DotfileEntry) -> None:
        """Create UI fields from parsed config."""
        if not parsed.fields:
            info = Adw.StatusPage()
            info.set_title("Empty Configuration")
            info.set_description("No configurable fields were found.")
            info.set_icon_name("dialog-information-symbolic")
            container.append(info)
            return

        # Format badge
        format_label = Gtk.Label(label=f"Format: {parsed.file_format}")
        format_label.add_css_class("dim-label")
        format_label.set_halign(Gtk.Align.START)
        format_label.set_margin_bottom(8)
        container.append(format_label)

        # Group fields by section
        current_group: Adw.PreferencesGroup | None = None
        current_section = ""

        for field in parsed.fields:
            if field.field_type == FieldType.COMMENT:
                # New section header
                current_group = Adw.PreferencesGroup()
                current_group.set_title(field.display_name)
                if field.comment:
                    current_group.set_description(field.comment)
                container.append(current_group)
                current_section = field.section
                continue

            if current_group is None or field.section != current_section:
                current_group = Adw.PreferencesGroup()
                if field.section:
                    current_group.set_title(field.section)
                    current_section = field.section
                container.append(current_group)

            row = self._create_field_row(field, parsed, entry)
            if row:
                current_group.add(row)

    def _create_field_row(self, field: ConfigField, parsed: ParsedConfig,
                          entry: DotfileEntry) -> Adw.ActionRow | None:
        """Create the appropriate Adw row for a config field."""
        config_path = entry.get_config_path()

        if field.field_type == FieldType.TOGGLE:
            row = Adw.SwitchRow()
            row.set_title(field.display_name)
            if field.comment:
                row.set_subtitle(field.comment)
            else:
                row.set_subtitle(field.key)
            active = field.value.lower().strip() in BOOL_TRUE
            row.set_active(active)
            row.connect("notify::active",
                        self._on_toggle_changed, field, config_path)
            return row

        if field.field_type == FieldType.SLIDER:
            row = Adw.ActionRow()
            row.set_title(field.display_name)
            if field.comment:
                row.set_subtitle(field.comment)
            else:
                row.set_subtitle(field.key)

            try:
                val = float(field.value)
            except ValueError:
                val = 0

            # Auto-detect reasonable range
            min_v, max_v, step = _auto_range(field.key, val)

            scale = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, min_v, max_v, step
            )
            scale.set_value(val)
            scale.set_size_request(200, -1)
            scale.set_draw_value(True)
            scale.set_valign(Gtk.Align.CENTER)

            # Value label
            val_label = Gtk.Label(label=str(int(val) if val == int(val) else val))
            val_label.set_valign(Gtk.Align.CENTER)
            val_label.set_margin_start(8)

            scale.connect("value-changed",
                          self._on_slider_changed, field, config_path,
                          val_label)
            row.add_suffix(scale)
            return row

        if field.field_type == FieldType.COLOR:
            row = Adw.ActionRow()
            row.set_title(field.display_name)
            if field.comment:
                row.set_subtitle(field.comment)
            else:
                row.set_subtitle(field.key)

            color = Gdk.RGBA()
            if field.value.startswith("#"):
                color.parse(field.value)
            else:
                color.parse("#000000")

            color_btn = Gtk.ColorDialogButton()
            dialog = Gtk.ColorDialog()
            color_btn.set_dialog(dialog)
            color_btn.set_rgba(color)
            color_btn.set_valign(Gtk.Align.CENTER)
            color_btn.connect("notify::rgba",
                              self._on_color_changed, field, config_path)
            row.add_suffix(color_btn)
            return row

        if field.field_type == FieldType.NUMBER:
            row = Adw.ActionRow()
            row.set_title(field.display_name)
            if field.comment:
                row.set_subtitle(field.comment)
            else:
                row.set_subtitle(field.key)

            try:
                val = float(field.value)
            except ValueError:
                val = 0

            spin = Gtk.SpinButton.new_with_range(-99999, 99999, 1)
            spin.set_value(val)
            spin.set_valign(Gtk.Align.CENTER)
            spin.connect("value-changed",
                         self._on_spin_changed, field, config_path)
            row.add_suffix(spin)
            return row

        if field.field_type == FieldType.PATH:
            row = Adw.ActionRow()
            row.set_title(field.display_name)
            if field.comment:
                row.set_subtitle(field.comment)
            else:
                row.set_subtitle(field.key)

            path_entry = Gtk.Entry()
            path_entry.set_text(field.value)
            path_entry.set_hexpand(True)
            path_entry.set_valign(Gtk.Align.CENTER)
            path_entry.set_size_request(300, -1)
            path_entry.connect("changed",
                               self._on_text_changed, field, config_path)

            browse_btn = Gtk.Button(icon_name="folder-open-symbolic")
            browse_btn.set_valign(Gtk.Align.CENTER)
            browse_btn.connect("clicked",
                               self._on_browse_path, path_entry, field,
                               config_path)

            row.add_suffix(path_entry)
            row.add_suffix(browse_btn)
            return row

        if field.field_type == FieldType.KEYBIND:
            row = Adw.ActionRow()
            row.set_title(field.display_name)
            subtitle = field.value
            if field.comment:
                subtitle = field.comment
            row.set_subtitle(subtitle)

            keybind_label = Gtk.Label(label=field.value)
            keybind_label.add_css_class("dim-label")
            keybind_label.set_valign(Gtk.Align.CENTER)
            keybind_label.set_ellipsize(Pango.EllipsizeMode.END)
            keybind_label.set_max_width_chars(40)
            row.add_suffix(keybind_label)
            return row

        if field.field_type == FieldType.FONT:
            row = Adw.ActionRow()
            row.set_title(field.display_name)
            if field.comment:
                row.set_subtitle(field.comment)
            else:
                row.set_subtitle(field.key)

            font_entry = Gtk.Entry()
            font_entry.set_text(field.value)
            font_entry.set_valign(Gtk.Align.CENTER)
            font_entry.set_size_request(250, -1)
            font_entry.connect("changed",
                               self._on_text_changed, field, config_path)
            row.add_suffix(font_entry)
            return row

        # Default: text entry
        row = Adw.ActionRow()
        row.set_title(field.display_name)
        if field.comment:
            row.set_subtitle(field.comment)
        else:
            row.set_subtitle(field.key)

        text_entry = Gtk.Entry()
        text_entry.set_text(field.value)
        text_entry.set_hexpand(True)
        text_entry.set_valign(Gtk.Align.CENTER)
        text_entry.set_size_request(300, -1)
        text_entry.connect("changed",
                           self._on_text_changed, field, config_path)
        row.add_suffix(text_entry)
        return row

    # ── Signal Handlers ─────────────────────────────────────────────

    def _on_sidebar_select(self, listbox: Gtk.ListBox,
                           row: Gtk.ListBoxRow | None) -> None:
        """Handle sidebar selection."""
        if row is None:
            return

        entry = getattr(row, "_dfm_entry", None)
        if entry is None:
            self.content_stack.set_visible_child_name("all-dotfiles")
            self.current_entry = None
        else:
            self.content_stack.set_visible_child_name(entry.name)
            self.current_entry = entry

    def _on_toggle_changed(self, switch_row: Adw.SwitchRow, _pspec,
                           field: ConfigField, config_path: str) -> None:
        """Handle toggle switch change."""
        new_val = "true" if switch_row.get_active() else "false"
        update_config_value(config_path, field, new_val)

    def _on_slider_changed(self, scale: Gtk.Scale, field: ConfigField,
                           config_path: str,
                           label: Gtk.Label) -> None:
        """Handle slider value change."""
        val = scale.get_value()
        str_val = str(int(val)) if val == int(val) else f"{val:.2f}"
        label.set_label(str_val)
        update_config_value(config_path, field, str_val)

    def _on_spin_changed(self, spin: Gtk.SpinButton, field: ConfigField,
                         config_path: str) -> None:
        """Handle spin button change."""
        val = spin.get_value()
        str_val = str(int(val)) if val == int(val) else str(val)
        update_config_value(config_path, field, str_val)

    def _on_color_changed(self, color_btn: Gtk.ColorDialogButton, _pspec,
                          field: ConfigField, config_path: str) -> None:
        """Handle color change."""
        rgba = color_btn.get_rgba()
        hex_color = "#{:02x}{:02x}{:02x}".format(
            int(rgba.red * 255),
            int(rgba.green * 255),
            int(rgba.blue * 255),
        )
        update_config_value(config_path, field, hex_color)

    def _on_text_changed(self, entry_widget: Gtk.Entry, field: ConfigField,
                         config_path: str) -> None:
        """Handle text entry change (debounced save)."""
        new_val = entry_widget.get_text()
        # Save after a short delay to avoid writing on every keystroke
        if hasattr(entry_widget, "_dfm_save_id"):
            GLib.source_remove(entry_widget._dfm_save_id)
        entry_widget._dfm_save_id = GLib.timeout_add(
            500,
            lambda: (update_config_value(config_path, field, new_val),
                     False)[1],
        )

    def _on_browse_path(self, _btn: Gtk.Button, path_entry: Gtk.Entry,
                        field: ConfigField, config_path: str) -> None:
        """Open a file chooser for path fields."""
        dialog = Gtk.FileDialog()
        dialog.set_title(f"Select path for {field.display_name}")
        dialog.open(self, None, self._on_path_selected, path_entry,
                    field, config_path)

    def _on_path_selected(self, dialog: Gtk.FileDialog,
                          result: Gio.AsyncResult,
                          path_entry: Gtk.Entry,
                          field: ConfigField, config_path: str) -> None:
        """Handle file selection."""
        try:
            file = dialog.open_finish(result)
            if file:
                path = file.get_path()
                path_entry.set_text(path)
                update_config_value(config_path, field, path)
        except GLib.Error:
            pass

    def _on_open_editor(self, _btn: Gtk.Button,
                        entry: DotfileEntry) -> None:
        """Open the config file in the default editor."""
        config_path = entry.get_config_path()
        if config_path:
            launcher = Gtk.FileLauncher.new(
                Gio.File.new_for_path(config_path)
            )
            launcher.launch(self, None, None)

    def _on_open_directory(self, _btn: Gtk.Button,
                           entry: DotfileEntry) -> None:
        """Open the directory containing the config file."""
        path = entry.path
        if not os.path.isdir(path):
            path = os.path.dirname(path)
        launcher = Gtk.FileLauncher.new(Gio.File.new_for_path(path))
        launcher.launch(self, None, None)

    def _on_export_single(self, _btn: Gtk.Button,
                          entry: DotfileEntry) -> None:
        """Export a single dotfile."""
        dialog = Gtk.FileDialog()
        dialog.set_title(f"Export {entry.display_name}")
        dialog.set_initial_name(f"{entry.name}_export.tar.gz")
        dialog.save(self, None, self._on_export_save_finish, [entry])

    def _on_view_raw(self, _btn: Gtk.Button,
                     entry: DotfileEntry) -> None:
        """Open the raw text viewer for this dotfile."""
        config_path = entry.get_config_path()
        if not config_path or not os.path.isfile(config_path):
            info = Adw.AlertDialog()
            info.set_heading("File Not Found")
            info.set_body(f"Cannot open: {config_path or entry.path}")
            info.add_response("ok", "OK")
            info.present(self)
            return

        viewer = TextViewerDialog(
            title=f"{entry.display_name} — Raw",
            file_path=config_path,
        )
        viewer.present(self)

    def _on_share_gist(self, _btn: Gtk.Button,
                       entry: DotfileEntry) -> None:
        """Upload this dotfile as a GitHub Gist."""
        if not is_gh_available():
            self._show_gh_missing_dialog()
            return
        if not is_gh_authenticated():
            self._show_gh_auth_dialog()
            return

        config_path = entry.get_config_path()
        if not config_path or not os.path.isfile(config_path):
            info = Adw.AlertDialog()
            info.set_heading("File Not Found")
            info.set_body(f"Cannot share: {config_path or entry.path}")
            info.add_response("ok", "OK")
            info.present(self)
            return

        # Confirm before uploading
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

    def _on_gist_confirmed(self, dialog: Adw.AlertDialog,
                           response: str, entry: DotfileEntry,
                           config_path: str) -> None:
        """Execute gist upload."""
        if response in ("secret", "public"):
            public = response == "public"
            desc = f"{entry.display_name} config (shared via DFM)"
            status = upload_gist(config_path, description=desc,
                                 public=public)

            info = Adw.AlertDialog()
            if status.success:
                info.set_heading("Gist Created")
                info.set_body(
                    f"{status.message}\n\n{status.url}"
                )
                info.add_response("copy", "Copy URL")
                info.add_response("ok", "OK")
                info.set_response_appearance(
                    "copy", Adw.ResponseAppearance.SUGGESTED
                )
                info.connect("response", self._on_gist_result_response,
                             status.url)
            else:
                info.set_heading("Gist Failed")
                info.set_body(status.message)
                info.add_response("ok", "OK")
            info.present(self)

    def _on_gist_result_response(self, dialog: Adw.AlertDialog,
                                 response: str, url: str) -> None:
        """Handle gist result dialog response."""
        if response == "copy":
            clipboard = Gdk.Display.get_default().get_clipboard()
            clipboard.set(url)

    def _show_gh_missing_dialog(self) -> None:
        """Show dialog when gh CLI is not installed."""
        info = Adw.AlertDialog()
        info.set_heading("GitHub CLI Not Found")
        info.set_body(
            "The GitHub CLI (gh) is required for GitHub features.\n\n"
            "Install it with:\n"
            "  sudo pacman -S github-cli\n\n"
            "Then authenticate:\n"
            "  gh auth login"
        )
        info.add_response("ok", "OK")
        info.present(self)

    def _show_gh_auth_dialog(self) -> None:
        """Show dialog when gh is not authenticated."""
        info = Adw.AlertDialog()
        info.set_heading("GitHub Authentication Required")
        info.set_body(
            "You need to authenticate with GitHub.\n\n"
            "Run in your terminal:\n"
            "  gh auth login\n\n"
            "Then restart DFM."
        )
        info.add_response("ok", "OK")
        info.present(self)

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

    def _on_import_file_selected(self, dialog: Gtk.FileDialog,
                                 result: Gio.AsyncResult) -> None:
        """Handle import file selection."""
        try:
            file = dialog.open_finish(result)
            if file:
                archive_path = file.get_path()
                # Show confirmation dialog
                confirm = Adw.AlertDialog()
                confirm.set_heading("Import Dotfiles")
                confirm.set_body(
                    f"Import dotfiles from:\n{archive_path}\n\n"
                    "Existing files will be backed up with .dfm_backup extension."
                )
                confirm.add_response("cancel", "Cancel")
                confirm.add_response("import", "Import")
                confirm.set_response_appearance(
                    "import", Adw.ResponseAppearance.SUGGESTED
                )
                confirm.connect("response", self._on_import_confirmed,
                                archive_path)
                confirm.present(self)
        except GLib.Error:
            pass

    def _on_import_confirmed(self, dialog: Adw.AlertDialog,
                             response: str, archive_path: str) -> None:
        """Execute the import."""
        if response == "import":
            actions = import_dotfiles(archive_path)
            done = sum(1 for a in actions if a["status"] == "done")
            errors = sum(1 for a in actions
                         if a["status"].startswith("error"))

            info = Adw.AlertDialog()
            info.set_heading("Import Complete")
            info.set_body(
                f"Imported: {done} files\n"
                f"Errors: {errors} files"
            )
            info.add_response("ok", "OK")
            info.present(self)

            # Refresh
            self._scan_and_populate()

    def _on_export_clicked(self, _btn) -> None:
        """Handle export button click."""
        enabled = [e for e in self.dotfiles if e.enabled]
        if not enabled:
            info = Adw.AlertDialog()
            info.set_heading("No Dotfiles Selected")
            info.set_body("Enable at least one dotfile to export.")
            info.add_response("ok", "OK")
            info.present(self)
            return

        dialog = Gtk.FileDialog()
        dialog.set_title("Export Dotfiles")
        dialog.set_initial_name("dotfiles_export.tar.gz")
        dialog.save(self, None, self._on_export_save_finish, enabled)

    def _on_export_save_finish(self, dialog: Gtk.FileDialog,
                               result: Gio.AsyncResult,
                               entries: list[DotfileEntry]) -> None:
        """Finish the export save dialog."""
        try:
            file = dialog.save_finish(result)
            if file:
                output_path = file.get_path()
                if output_path.endswith(".tar.gz"):
                    output_dir = os.path.dirname(output_path)
                else:
                    output_dir = output_path

                archive = export_dotfiles(entries, output_dir)

                info = Adw.AlertDialog()
                info.set_heading("Export Complete")
                info.set_body(f"Dotfiles exported to:\n{archive}")
                info.add_response("ok", "OK")
                info.present(self)
        except GLib.Error:
            pass

    def _on_about(self, *_args) -> None:
        """Show the about dialog."""
        about = Adw.AboutDialog()
        about.set_application_name("DFM")
        about.set_version("1.0.0")
        about.set_developer_name("DFM Contributors")
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_comments(
            "A graphical dotfile manager for Arch Linux.\n"
            "Detect, configure, import/export, and sync your dotfiles with GitHub."
        )
        about.set_application_icon("preferences-other")
        about.present(self)


# ── Helpers ─────────────────────────────────────────────────────────

def _categorize(entry: DotfileEntry) -> str:
    """Categorize a dotfile for grouping."""
    name = entry.name.lower()
    display = entry.display_name.lower()

    terminals = {"alacritty", "kitty", "foot", "wezterm"}
    shells = {"bash", "zsh", "fish", "shell"}
    wms = {"i3", "sway", "hypr", "hyprland", "bspwm", "awesome",
           "openbox", "herbstluftwm", "fluxbox"}
    bars = {"waybar", "polybar"}
    launchers = {"rofi", "wofi"}
    notifications = {"dunst", "mako"}
    editors = {"vim", "nvim", "neovim", "nano"}
    media = {"mpv", "cava", "pipewire", "pulse", "wireplumber"}

    if any(t in name or t in display for t in terminals):
        return "Terminal Emulators"
    if any(s in name or s in display for s in shells):
        return "Shells"
    if any(w in name or w in display for w in wms):
        return "Window Managers"
    if any(b in name or b in display for b in bars):
        return "Status Bars"
    if any(l in name or l in display for l in launchers):
        return "Launchers"
    if any(n in name or n in display for n in notifications):
        return "Notifications"
    if any(e in name or e in display for e in editors):
        return "Editors"
    if any(m in name or m in display for m in media):
        return "Media"
    if "gtk" in name or "qt" in name or "font" in name or "theme" in display:
        return "Appearance"
    if "git" in name:
        return "Development"
    return "System"


def _auto_range(key: str, current_val: float) -> tuple[float, float, float]:
    """Determine a reasonable range for a slider based on key name."""
    key_lower = key.lower()

    if "opacity" in key_lower or "alpha" in key_lower or "dim" in key_lower:
        return (0.0, 1.0, 0.05)
    if "gap" in key_lower or "margin" in key_lower or "padding" in key_lower:
        return (0, max(50, current_val * 2), 1)
    if "border" in key_lower or "radius" in key_lower or "rounding" in key_lower:
        return (0, max(30, current_val * 2), 1)
    if "size" in key_lower or "width" in key_lower or "height" in key_lower:
        return (0, max(200, current_val * 2), 1)
    if "speed" in key_lower or "rate" in key_lower:
        return (0, max(100, current_val * 2), 1)
    if "delay" in key_lower or "timeout" in key_lower or "interval" in key_lower:
        return (0, max(10000, current_val * 2), 100)
    if "scale" in key_lower:
        return (0.5, 3.0, 0.1)
    if "blur" in key_lower:
        return (0, max(20, current_val * 2), 1)
    if "columns" in key_lower or "rows" in key_lower:
        return (1, max(20, current_val * 2), 1)

    # Generic
    return (0, max(100, current_val * 2), 1)
