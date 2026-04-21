"""Pull handler with overwrite preview for the GitHub sync section."""

import os
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from dfm.core.github_sync import (
    is_gh_available, is_gh_authenticated, pull_dotfiles, get_repo_path,
)


_SKIP_FILES = {"dfm_manifest.json", "README.md", "LICENSE", ".gitignore"}


def on_pull_clicked(section, _btn: Gtk.Button) -> None:
    """Handle pull: check prerequisites, show what will change, confirm."""
    if not is_gh_available():
        section._show_gh_missing_dialog()
        return
    if not is_gh_authenticated():
        section._show_gh_auth_dialog()
        return

    repo_path = get_repo_path()
    if not repo_path:
        section._alert("No Repository",
                       "Create or clone a dotfiles repo first.")
        return

    _show_pull_diff_dialog(section, repo_path)


def _walk_repo(repo_path: str) -> tuple[list[str], list[str]]:
    """Return (overwrite_files, new_files) for a pull preview."""
    home = str(Path.home())
    overwrite_files: list[str] = []
    new_files: list[str] = []

    if not os.path.isdir(repo_path):
        return overwrite_files, new_files

    for root, dirs, files in os.walk(repo_path):
        if ".git" in root.split(os.sep):
            continue
        dirs[:] = [d for d in dirs if d != ".git"]
        for fname in files:
            if fname in _SKIP_FILES:
                continue
            src = os.path.join(root, fname)
            rel = os.path.relpath(src, repo_path)
            dest = os.path.join(home, rel)
            if os.path.exists(dest):
                overwrite_files.append(rel)
            else:
                new_files.append(rel)

    return overwrite_files, new_files


def _show_pull_diff_dialog(section, repo_path: str) -> None:
    """Show what files would be overwritten by a pull."""
    overwrite_files, new_files = _walk_repo(repo_path)

    lines: list[str] = []
    if overwrite_files:
        lines.append(
            f"{len(overwrite_files)} file(s) will be overwritten "
            "(backups created automatically):"
        )
        for f in overwrite_files[:15]:
            lines.append(f"  ●  {f}")
        if len(overwrite_files) > 15:
            lines.append(f"  ... and {len(overwrite_files) - 15} more")
    if new_files:
        if lines:
            lines.append("")
        lines.append(f"{len(new_files)} new file(s) will be added:")
        for f in new_files[:15]:
            lines.append(f"  ●  {f}")
        if len(new_files) > 15:
            lines.append(f"  ... and {len(new_files) - 15} more")
    if not lines:
        lines.append("No files found in the repository to pull.")

    dialog = Adw.AlertDialog()
    dialog.set_heading("Pull Dotfiles from GitHub")
    dialog.set_body("\n".join(lines))
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("pull", "Pull")
    dialog.set_response_appearance("pull", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("cancel")
    dialog.set_close_response("cancel")
    dialog.connect("response", _on_pull_confirmed, section)
    dialog.present(section._window)


def _on_pull_confirmed(dialog: Adw.AlertDialog, response: str, section) -> None:
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
    section._alert(heading, body)

    if status.success:
        section.refresh_status()
        if section._on_rescan:
            section._on_rescan()
