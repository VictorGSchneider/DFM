"""Push handler with diff preview for the GitHub sync section."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from dfm.core.scanner import DotfileEntry
from dfm.core.github_sync import (
    is_gh_available, is_gh_authenticated, push_dotfiles, get_repo_path,
)
from dfm.core.diff_utils import repo_diff_summary, format_diff_stats


def on_push_clicked(section, _btn: Gtk.Button) -> None:
    """Handle push: check prerequisites, show diff, then confirm."""
    if not is_gh_available():
        section._show_gh_missing_dialog()
        return
    if not is_gh_authenticated():
        section._show_gh_auth_dialog()
        return

    repo_path = get_repo_path()
    if not repo_path:
        section._alert(
            "No Repository",
            "Create or clone a dotfiles repo first using the Setup section below.",
        )
        return

    entries = section._get_dotfiles()
    enabled = [e for e in entries if e.enabled]
    if not enabled:
        section._alert("No Dotfiles Selected",
                       "Enable at least one dotfile to push.")
        return

    diff_items = repo_diff_summary(repo_path, enabled)
    changed = [d for d in diff_items if d["status"] != "unchanged"]

    if not changed:
        section._alert(
            "Nothing to Push",
            "All enabled dotfiles are already up to date with the repository.",
        )
        return

    _show_push_diff_dialog(section, changed, enabled)


def _show_push_diff_dialog(section, diff_items: list[dict],
                           entries: list[DotfileEntry]) -> None:
    """Show a dialog with the diff summary before pushing."""
    lines: list[str] = []
    new_count = mod_count = del_count = 0

    for item in diff_items:
        status = item["status"]
        name = item.get("display_name") or item.get("name", "?")
        stats = format_diff_stats(item.get("adds", 0), item.get("dels", 0))

        if status == "new":
            lines.append(f"  ●  {name}  [new file]")
            new_count += 1
        elif status == "modified":
            lines.append(f"  ●  {name}  ({stats})")
            mod_count += 1
        elif status == "deleted":
            lines.append(f"  ●  {name}  [deleted]")
            del_count += 1

    summary_parts = []
    if new_count:
        summary_parts.append(f"{new_count} new")
    if mod_count:
        summary_parts.append(f"{mod_count} modified")
    if del_count:
        summary_parts.append(f"{del_count} deleted")

    body = f"Changes: {', '.join(summary_parts)}\n\n" + "\n".join(lines)

    dialog = Adw.AlertDialog()
    dialog.set_heading("Review Changes Before Push")
    dialog.set_body(body)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("push", "Push")
    dialog.set_response_appearance("push", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("cancel")
    dialog.set_close_response("cancel")
    dialog.connect("response", _on_push_confirmed, section, entries)
    dialog.present(section._window)


def _on_push_confirmed(dialog: Adw.AlertDialog, response: str,
                       section, entries: list[DotfileEntry]) -> None:
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
    section._alert(heading, body)
    if status.success:
        section.refresh_status()
