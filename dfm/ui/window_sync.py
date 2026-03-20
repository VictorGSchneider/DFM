"""GitHub Sync UI section for the All Dotfiles page.

Provides status display, push/pull with diff previews, commit history,
gist import, and repo setup controls.
"""

import os
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Pango

from dfm.core.scanner import DotfileEntry
from dfm.core.github_sync import (
    is_gh_available, is_gh_authenticated, get_gh_username,
    upload_gist, import_gist, list_gists, init_repo, clone_repo,
    push_dotfiles, pull_dotfiles, get_repo_status, get_repo_path,
    save_repo_path, get_commit_history,
)
from dfm.core.diff_utils import repo_diff_summary, format_diff_stats


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

        # Widgets that need refreshing
        self._status_group: Adw.PreferencesGroup | None = None
        self._history_group: Adw.PreferencesGroup | None = None

    # ── Public API ──────────────────────────────────────────────────

    def build(self) -> Gtk.Box:
        """Build the full sync section and return the top-level box."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        # Section title
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

        # Status group
        self._status_group = Adw.PreferencesGroup()
        self._status_group.set_title("Status")
        self._populate_status_group()
        box.append(self._status_group)

        # Actions group
        box.append(self._build_actions_group())

        # Commit history group
        self._history_group = Adw.PreferencesGroup()
        self._history_group.set_title("Commit History")
        self._history_group.set_description("Recent commits in the dotfiles repo")
        self._populate_history_group()
        box.append(self._history_group)

        # Setup group
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

        # GitHub CLI row
        gh_row = Adw.ActionRow()
        gh_row.set_title("GitHub CLI")
        if not status["gh_available"]:
            gh_row.set_subtitle("Not installed")
            icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            icon.add_css_class("warning")
        elif not status["gh_authenticated"]:
            gh_row.set_subtitle("Not authenticated \u2014 run 'gh auth login'")
            icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        else:
            gh_row.set_subtitle(f"Authenticated as {status['username']}")
            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        icon.set_valign(Gtk.Align.CENTER)
        gh_row.add_suffix(icon)
        self._status_group.add(gh_row)

        # Repo row
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
            repo_row.set_subtitle(" \u00b7 ".join(parts))
            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        elif status["configured"]:
            repo_row.set_subtitle(
                f"Configured but not found: {status['path']}"
            )
            icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        else:
            repo_row.set_subtitle("Not configured \u2014 create or clone a repo")
            icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
        icon.set_valign(Gtk.Align.CENTER)
        repo_row.add_suffix(icon)

        # Refresh button
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

        # Push row
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
        group.add(push_row)

        # Pull row
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
        group.add(pull_row)

        # Import from Gist row
        gist_row = Adw.ActionRow()
        gist_row.set_title("Import from Gist")
        gist_row.set_subtitle(
            "Download a GitHub Gist and save it locally"
        )
        gist_btn = Gtk.Button(label="Import")
        gist_btn.add_css_class("flat")
        gist_btn.set_valign(Gtk.Align.CENTER)
        gist_btn.connect("clicked", self._on_import_gist_clicked)
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
            empty_row.set_subtitle(
                "Push dotfiles to create the first commit"
            )
            self._history_group.add(empty_row)
            return

        for commit in commits:
            row = Adw.ExpanderRow()
            row.set_title(
                GLib.markup_escape_text(commit.get("message", ""))
            )

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
            row.set_subtitle(" \u00b7 ".join(subtitle_parts))

            # Add child rows for each changed file
            for fname in files:
                file_row = Adw.ActionRow()
                file_row.set_title(GLib.markup_escape_text(fname))
                file_icon = Gtk.Image.new_from_icon_name(
                    "document-properties-symbolic"
                )
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
        init_row.set_subtitle(
            "Create a new private repo on GitHub and clone it"
        )
        init_btn = Gtk.Button(label="Create")
        init_btn.add_css_class("flat")
        init_btn.set_valign(Gtk.Align.CENTER)
        init_btn.connect("clicked", self._on_init_repo_clicked)
        init_row.add_suffix(init_btn)
        init_row.set_activatable_widget(init_btn)
        group.add(init_row)

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
        group.add(clone_row)

        return group

    # ── Push handler (diff-before-push) ─────────────────────────────

    def _on_push_clicked(self, _btn: Gtk.Button) -> None:
        """Handle push: check prerequisites, show diff, then confirm."""
        if not is_gh_available():
            self._show_gh_missing_dialog()
            return
        if not is_gh_authenticated():
            self._show_gh_auth_dialog()
            return

        repo_path = get_repo_path()
        if not repo_path:
            self._alert("No Repository",
                        "Create or clone a dotfiles repo first using "
                        "the Setup section below.")
            return

        entries = self._get_dotfiles()
        enabled = [e for e in entries if e.enabled]
        if not enabled:
            self._alert("No Dotfiles Selected",
                        "Enable at least one dotfile to push.")
            return

        # Compute diff summary
        diff_items = repo_diff_summary(repo_path, enabled)
        changed = [d for d in diff_items if d["status"] != "unchanged"]

        if not changed:
            self._alert("Nothing to Push",
                        "All enabled dotfiles are already up to date "
                        "with the repository.")
            return

        self._show_push_diff_dialog(changed, enabled)

    def _show_push_diff_dialog(self, diff_items: list[dict],
                               entries: list[DotfileEntry]) -> None:
        """Show a dialog with the diff summary before pushing."""
        dialog = Adw.AlertDialog()
        dialog.set_heading("Review Changes Before Push")

        # Build a readable body
        lines = []
        new_count = 0
        mod_count = 0
        del_count = 0

        for item in diff_items:
            status = item["status"]
            name = item.get("display_name") or item.get("name", "?")
            stats = format_diff_stats(item.get("adds", 0), item.get("dels", 0))

            if status == "new":
                lines.append(f"  \u25cf  {name}  [new file]")
                new_count += 1
            elif status == "modified":
                lines.append(f"  \u25cf  {name}  ({stats})")
                mod_count += 1
            elif status == "deleted":
                lines.append(f"  \u25cf  {name}  [deleted]")
                del_count += 1

        summary_parts = []
        if new_count:
            summary_parts.append(f"{new_count} new")
        if mod_count:
            summary_parts.append(f"{mod_count} modified")
        if del_count:
            summary_parts.append(f"{del_count} deleted")

        header = f"Changes: {', '.join(summary_parts)}\n\n"
        body = header + "\n".join(lines)

        dialog.set_body(body)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("push", "Push")
        dialog.set_response_appearance(
            "push", Adw.ResponseAppearance.SUGGESTED
        )
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_push_confirmed, entries)
        dialog.present(self._window)

    def _on_push_confirmed(self, dialog: Adw.AlertDialog,
                           response: str,
                           entries: list[DotfileEntry]) -> None:
        """Execute the push after user confirmation."""
        if response != "push":
            return

        status = push_dotfiles(entries)
        heading = "Push Complete" if status.success else "Push Failed"
        body = status.message
        if status.details:
            body += "\n\n" + "\n".join(status.details[:20])
            if len(status.details) > 20:
                body += f"\n... and {len(status.details) - 20} more"
        self._alert(heading, body)
        if status.success:
            self.refresh_status()

    # ── Pull handler (diff-before-pull) ─────────────────────────────

    def _on_pull_clicked(self, _btn: Gtk.Button) -> None:
        """Handle pull: check prerequisites, show what will change, confirm."""
        if not is_gh_available():
            self._show_gh_missing_dialog()
            return
        if not is_gh_authenticated():
            self._show_gh_auth_dialog()
            return

        repo_path = get_repo_path()
        if not repo_path:
            self._alert("No Repository",
                        "Create or clone a dotfiles repo first.")
            return

        # Build a preview of what the pull will overwrite
        self._show_pull_diff_dialog(repo_path)

    def _show_pull_diff_dialog(self, repo_path: str) -> None:
        """Show what files would be overwritten by a pull."""
        home = str(Path.home())
        overwrite_files = []
        new_files = []

        if os.path.isdir(repo_path):
            for root, dirs, files in os.walk(repo_path):
                if ".git" in root.split(os.sep):
                    continue
                dirs[:] = [d for d in dirs if d != ".git"]
                for fname in files:
                    if fname in ("dfm_manifest.json", "README.md",
                                 "LICENSE", ".gitignore"):
                        continue
                    src = os.path.join(root, fname)
                    rel = os.path.relpath(src, repo_path)
                    dest = os.path.join(home, rel)
                    if os.path.exists(dest):
                        overwrite_files.append(rel)
                    else:
                        new_files.append(rel)

        lines = []
        if overwrite_files:
            lines.append(
                f"{len(overwrite_files)} file(s) will be overwritten "
                "(backups created automatically):"
            )
            for f in overwrite_files[:15]:
                lines.append(f"  \u25cf  {f}")
            if len(overwrite_files) > 15:
                lines.append(
                    f"  ... and {len(overwrite_files) - 15} more"
                )
        if new_files:
            if lines:
                lines.append("")
            lines.append(f"{len(new_files)} new file(s) will be added:")
            for f in new_files[:15]:
                lines.append(f"  \u25cf  {f}")
            if len(new_files) > 15:
                lines.append(f"  ... and {len(new_files) - 15} more")

        if not lines:
            lines.append("No files found in the repository to pull.")

        dialog = Adw.AlertDialog()
        dialog.set_heading("Pull Dotfiles from GitHub")
        dialog.set_body("\n".join(lines))
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("pull", "Pull")
        dialog.set_response_appearance(
            "pull", Adw.ResponseAppearance.SUGGESTED
        )
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_pull_confirmed)
        dialog.present(self._window)

    def _on_pull_confirmed(self, dialog: Adw.AlertDialog,
                           response: str) -> None:
        """Execute pull after confirmation."""
        if response != "pull":
            return

        status = pull_dotfiles()
        heading = "Pull Complete" if status.success else "Pull Failed"
        body = status.message
        if status.details:
            body += "\n\n" + "\n".join(status.details[:20])
            if len(status.details) > 20:
                body += f"\n... and {len(status.details) - 20} more"
        self._alert(heading, body)

        if status.success:
            self.refresh_status()
            if self._on_rescan:
                self._on_rescan()

    # ── Import from Gist ────────────────────────────────────────────

    def _on_import_gist_clicked(self, _btn: Gtk.Button) -> None:
        """Show the import-from-gist dialog."""
        if not is_gh_available():
            self._show_gh_missing_dialog()
            return
        if not is_gh_authenticated():
            self._show_gh_auth_dialog()
            return

        dialog = Adw.AlertDialog()
        dialog.set_heading("Import from Gist")
        dialog.set_body("Enter a Gist ID or URL and the local path to save to.")

        # Build an extra child widget with two entry fields
        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12
        )
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
        target_entry.set_text(
            os.path.join(str(Path.home()), ".config", "")
        )
        target_group = Adw.PreferencesGroup()
        target_group.add(target_entry)
        content_box.append(target_group)

        dialog.set_extra_child(content_box)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("import", "Import")
        dialog.set_response_appearance(
            "import", Adw.ResponseAppearance.SUGGESTED
        )
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect(
            "response", self._on_import_gist_response,
            gist_entry, target_entry,
        )
        dialog.present(self._window)

    def _on_import_gist_response(self, dialog: Adw.AlertDialog,
                                 response: str,
                                 gist_entry: Adw.EntryRow,
                                 target_entry: Adw.EntryRow) -> None:
        """Handle the import gist dialog response."""
        if response != "import":
            return

        gist_id = gist_entry.get_text().strip()
        target_path = target_entry.get_text().strip()

        if not gist_id:
            self._alert("Missing Gist ID",
                        "Please enter a Gist ID or URL.")
            return
        if not target_path:
            self._alert("Missing Target Path",
                        "Please enter a path to save the file.")
            return

        status = import_gist(gist_id, target_path)
        heading = "Import Complete" if status.success else "Import Failed"
        self._alert(heading, status.message)

        if status.success and self._on_rescan:
            self._on_rescan()

    # ── Setup handlers ──────────────────────────────────────────────

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
        confirm.set_default_response("cancel")
        confirm.set_close_response("cancel")
        confirm.connect("response", self._on_init_confirmed)
        confirm.present(self._window)

    def _on_init_confirmed(self, dialog: Adw.AlertDialog,
                           response: str) -> None:
        """Execute repo creation."""
        if response != "create":
            return

        status = init_repo()
        heading = "Repo Created" if status.success else "Creation Failed"
        body = status.message
        if status.url:
            body += f"\n\n{status.url}"
        self._alert(heading, body)
        if status.success:
            self.refresh_status()

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
        confirm.set_default_response("cancel")
        confirm.set_close_response("cancel")
        confirm.connect("response", self._on_clone_confirmed)
        confirm.present(self._window)

    def _on_clone_confirmed(self, dialog: Adw.AlertDialog,
                            response: str) -> None:
        """Execute clone."""
        if response != "clone":
            return

        status = clone_repo()
        heading = "Clone Complete" if status.success else "Clone Failed"
        body = status.message
        if status.url:
            body += f"\n\n{status.url}"
        self._alert(heading, body)
        if status.success:
            self.refresh_status()

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
        # Collect all rows first, then remove them to avoid
        # mutation-during-iteration issues.
        rows = []

        def _collect_rows(widget):
            if isinstance(widget, (Adw.ActionRow, Adw.ExpanderRow)):
                rows.append(widget)
                return  # don't recurse into row children
            child = widget.get_first_child()
            while child is not None:
                _collect_rows(child)
                child = child.get_next_sibling()

        _collect_rows(group)
        for row in rows:
            group.remove(row)
