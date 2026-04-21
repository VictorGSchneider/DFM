"""GitHub Sync UI section for the All Dotfiles page.

Provides status display, push/pull with diff previews, commit history,
gist import, and repo setup controls.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from dfm.core.github_sync import get_repo_status, get_commit_history
from dfm.ui.window_sync_push import on_push_clicked
from dfm.ui.window_sync_pull import on_pull_clicked
from dfm.ui.window_sync_gist import on_import_gist_clicked
from dfm.ui.window_sync_setup import (
    on_init_repo_clicked, on_clone_repo_clicked,
)


class SyncSection:
    """Builds and manages the GitHub Sync UI section."""

    def __init__(self, window: Adw.ApplicationWindow,
                 get_dotfiles_cb, on_rescan_cb) -> None:
        """Initialise the sync section.

        Args:
            window: Parent window used to present dialogs.
            get_dotfiles_cb: Callable returning the current list[DotfileEntry].
            on_rescan_cb: Callable to trigger a rescan after pull.
        """
        self._window = window
        self._get_dotfiles = get_dotfiles_cb
        self._on_rescan = on_rescan_cb

        self._status_group: Adw.PreferencesGroup | None = None
        self._history_group: Adw.PreferencesGroup | None = None

    # ── Public API ──────────────────────────────────────────────────

    def build(self) -> Gtk.Box:
        """Build the full sync section and return the top-level box."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        separator = Gtk.Separator()
        separator.set_margin_top(16)
        box.append(separator)

        title = Gtk.Label(label="GitHub Sync")
        title.add_css_class("title-1")
        title.set_halign(Gtk.Align.START)
        title.set_margin_top(16)
        box.append(title)

        desc = Gtk.Label(
            label="Sync your dotfiles with a GitHub repository. "
                  "Uses the standard dotfiles repo approach with full "
                  "directory structure, commit history, and bidirectional sync."
        )
        desc.add_css_class("dim-label")
        desc.set_halign(Gtk.Align.START)
        desc.set_wrap(True)
        desc.set_margin_bottom(12)
        box.append(desc)

        self._status_group = Adw.PreferencesGroup()
        self._status_group.set_title("Status")
        self._populate_status_group()
        box.append(self._status_group)

        box.append(self._build_actions_group())

        self._history_group = Adw.PreferencesGroup()
        self._history_group.set_title("Commit History")
        self._history_group.set_description("Recent commits in the dotfiles repo")
        self._populate_history_group()
        box.append(self._history_group)

        box.append(self._build_setup_group())

        return box

    def refresh_status(self) -> None:
        """Refresh the status display and commit history."""
        if self._status_group is not None:
            self._clear_group(self._status_group)
            self._populate_status_group()
        if self._history_group is not None:
            self._clear_group(self._history_group)
            self._populate_history_group()

    # ── Status Group ────────────────────────────────────────────────

    def _populate_status_group(self) -> None:
        """Fill the status preference group with current info."""
        status = get_repo_status()

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
        self._status_group.add(gh_row)

        repo_row = Adw.ActionRow()
        repo_row.set_title("Dotfiles Repository")
        if status["configured"] and status.get("exists"):
            parts = []
            if status.get("path"):
                parts.append(status["path"])
            if status.get("branch"):
                parts.append(f"branch: {status['branch']}")
            if status.get("last_commit"):
                parts.append(status["last_commit"])
            repo_row.set_subtitle(" · ".join(parts))
            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        elif status["configured"]:
            repo_row.set_subtitle(f"Configured but not found: {status['path']}")
            icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        else:
            repo_row.set_subtitle("Not configured — create or clone a repo")
            icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
        icon.set_valign(Gtk.Align.CENTER)
        repo_row.add_suffix(icon)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_valign(Gtk.Align.CENTER)
        refresh_btn.add_css_class("flat")
        refresh_btn.set_tooltip_text("Refresh status")
        refresh_btn.connect("clicked", lambda _b: self.refresh_status())
        repo_row.add_suffix(refresh_btn)

        self._status_group.add(repo_row)

    # ── Actions Group ───────────────────────────────────────────────

    def _build_actions_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup()
        group.set_title("Actions")

        push_row = Adw.ActionRow()
        push_row.set_title("Push to GitHub")
        push_row.set_subtitle("Copy enabled dotfiles to the repo, commit, and push")
        push_btn = Gtk.Button(label="Push")
        push_btn.add_css_class("suggested-action")
        push_btn.set_valign(Gtk.Align.CENTER)
        push_btn.connect("clicked", lambda b: on_push_clicked(self, b))
        push_row.add_suffix(push_btn)
        push_row.set_activatable_widget(push_btn)
        group.add(push_row)

        pull_row = Adw.ActionRow()
        pull_row.set_title("Pull from GitHub")
        pull_row.set_subtitle("Download dotfiles from repo and install to home")
        pull_btn = Gtk.Button(label="Pull")
        pull_btn.add_css_class("flat")
        pull_btn.set_valign(Gtk.Align.CENTER)
        pull_btn.connect("clicked", lambda b: on_pull_clicked(self, b))
        pull_row.add_suffix(pull_btn)
        pull_row.set_activatable_widget(pull_btn)
        group.add(pull_row)

        gist_row = Adw.ActionRow()
        gist_row.set_title("Import from Gist")
        gist_row.set_subtitle("Download a GitHub Gist and save it locally")
        gist_btn = Gtk.Button(label="Import")
        gist_btn.add_css_class("flat")
        gist_btn.set_valign(Gtk.Align.CENTER)
        gist_btn.connect("clicked", lambda b: on_import_gist_clicked(self, b))
        gist_row.add_suffix(gist_btn)
        gist_row.set_activatable_widget(gist_btn)
        group.add(gist_row)

        return group

    # ── Commit History Group ────────────────────────────────────────

    def _populate_history_group(self) -> None:
        """Fill the commit history group with recent commits."""
        commits = get_commit_history(limit=15)

        if not commits:
            empty_row = Adw.ActionRow()
            empty_row.set_title("No commits yet")
            empty_row.set_subtitle("Push dotfiles to create the first commit")
            self._history_group.add(empty_row)
            return

        for commit in commits:
            row = Adw.ExpanderRow()
            row.set_title(GLib.markup_escape_text(commit.get("message", "")))

            short_hash = commit.get("short_hash", "")
            rel_date = commit.get("relative_date", "")
            files = commit.get("files_changed", [])
            file_count = len(files)
            subtitle_parts = []
            if short_hash:
                subtitle_parts.append(short_hash)
            if rel_date:
                subtitle_parts.append(rel_date)
            if file_count:
                noun = "file" if file_count == 1 else "files"
                subtitle_parts.append(f"{file_count} {noun} changed")
            row.set_subtitle(" · ".join(subtitle_parts))

            for fname in files:
                file_row = Adw.ActionRow()
                file_row.set_title(GLib.markup_escape_text(fname))
                file_icon = Gtk.Image.new_from_icon_name("document-properties-symbolic")
                file_icon.set_valign(Gtk.Align.CENTER)
                file_row.add_prefix(file_icon)
                row.add_row(file_row)

            self._history_group.add(row)

    # ── Setup Group ─────────────────────────────────────────────────

    def _build_setup_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup()
        group.set_title("Setup")
        group.set_description(
            "Requires GitHub CLI (gh). Install: sudo pacman -S github-cli"
        )

        init_row = Adw.ActionRow()
        init_row.set_title("Create New Dotfiles Repo")
        init_row.set_subtitle("Create a new private repo on GitHub and clone it")
        init_btn = Gtk.Button(label="Create")
        init_btn.add_css_class("flat")
        init_btn.set_valign(Gtk.Align.CENTER)
        init_btn.connect("clicked", lambda b: on_init_repo_clicked(self, b))
        init_row.add_suffix(init_btn)
        init_row.set_activatable_widget(init_btn)
        group.add(init_row)

        clone_row = Adw.ActionRow()
        clone_row.set_title("Clone Existing Repo")
        clone_row.set_subtitle("Clone your existing dotfiles repo from GitHub")
        clone_btn = Gtk.Button(label="Clone")
        clone_btn.add_css_class("flat")
        clone_btn.set_valign(Gtk.Align.CENTER)
        clone_btn.connect("clicked", lambda b: on_clone_repo_clicked(self, b))
        clone_row.add_suffix(clone_btn)
        clone_row.set_activatable_widget(clone_btn)
        group.add(clone_row)

        return group

    # ── Utility helpers ─────────────────────────────────────────────

    def _alert(self, heading: str, body: str) -> None:
        """Show a simple informational alert dialog."""
        info = Adw.AlertDialog()
        info.set_heading(heading)
        info.set_body(body)
        info.add_response("ok", "OK")
        info.present(self._window)

    def _show_gh_missing_dialog(self) -> None:
        """Show dialog when gh CLI is not installed."""
        self._alert(
            "GitHub CLI Not Found",
            "The GitHub CLI (gh) is required for GitHub features.\n\n"
            "Install it with:\n"
            "  sudo pacman -S github-cli\n\n"
            "Then run: gh auth login",
        )

    def _show_gh_auth_dialog(self) -> None:
        """Show dialog when gh is not authenticated."""
        self._alert(
            "GitHub Authentication Required",
            "You need to authenticate with GitHub.\n\n"
            "Run in your terminal:\n"
            "  gh auth login\n\n"
            "Then restart DFM.",
        )

    @staticmethod
    def _clear_group(group: Adw.PreferencesGroup) -> None:
        """Remove all rows from a PreferencesGroup."""
        rows = []

        def _collect_rows(widget):
            if isinstance(widget, (Adw.ActionRow, Adw.ExpanderRow)):
                rows.append(widget)
                return
            child = widget.get_first_child()
            while child is not None:
                _collect_rows(child)
                child = child.get_next_sibling()

        _collect_rows(group)
        for row in rows:
            group.remove(row)
