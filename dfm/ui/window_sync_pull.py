"""Pull handler with overwrite preview for the GitHub sync section."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from dfm.core.github_sync import pull_dotfiles, get_repo_path, pull_preview


def on_pull_clicked(section, _btn: Gtk.Button) -> None:
    """Handle pull: check prerequisites, show what will change, confirm."""
    section.require_remote_access(lambda: _after_auth(section))


def _after_auth(section) -> None:
    repo_path = get_repo_path()
    if not repo_path:
        section._alert("No Repository",
                       "Create, clone or choose a dotfiles repo first.")
        return

    _show_pull_diff_dialog(section, repo_path)


def _show_pull_diff_dialog(section, repo_path: str) -> None:
    """Show what files would be overwritten by a pull."""
    overwrite_files, new_files = pull_preview(repo_path)

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
        lines.append("Nothing to pull: your dotfiles already match the repository.")

    dialog = Adw.AlertDialog()
    dialog.set_heading("Pull Dotfiles")
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

    section.run_task(
        "Pulling…",
        pull_dotfiles,
        lambda status, error: _pull_done(section, status, error),
    )


def _pull_done(section, status, error) -> None:
    if error is not None:
        section._alert("Pull Failed", str(error))
        return
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
