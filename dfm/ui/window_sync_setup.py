"""Repo init/clone handlers for the GitHub sync section."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from dfm.core.github_sync import (
    is_gh_available, is_gh_authenticated, init_repo, clone_repo,
)


def on_init_repo_clicked(section, _btn: Gtk.Button) -> None:
    """Handle create new repo."""
    if not is_gh_available():
        section._show_gh_missing_dialog()
        return
    if not is_gh_authenticated():
        section._show_gh_auth_dialog()
        return

    confirm = Adw.AlertDialog()
    confirm.set_heading("Create Dotfiles Repository")
    confirm.set_body(
        "Create a new private 'dotfiles' repo on GitHub?\n\n"
        "The repo will be cloned to ~/.dotfiles locally."
    )
    confirm.add_response("cancel", "Cancel")
    confirm.add_response("create", "Create")
    confirm.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
    confirm.set_default_response("cancel")
    confirm.set_close_response("cancel")
    confirm.connect("response", _on_init_confirmed, section)
    confirm.present(section._window)


def _on_init_confirmed(dialog: Adw.AlertDialog, response: str, section) -> None:
    if response != "create":
        return

    status = init_repo()
    heading = "Repo Created" if status.success else "Creation Failed"
    body = status.message
    if status.url:
        body += f"\n\n{status.url}"
    section._alert(heading, body)
    if status.success:
        section.refresh_status()


def on_clone_repo_clicked(section, _btn: Gtk.Button) -> None:
    """Handle clone existing repo."""
    if not is_gh_available():
        section._show_gh_missing_dialog()
        return
    if not is_gh_authenticated():
        section._show_gh_auth_dialog()
        return

    confirm = Adw.AlertDialog()
    confirm.set_heading("Clone Dotfiles Repository")
    confirm.set_body(
        "Clone your existing 'dotfiles' repo from GitHub?\n\n"
        "It will be cloned to ~/.dotfiles locally."
    )
    confirm.add_response("cancel", "Cancel")
    confirm.add_response("clone", "Clone")
    confirm.set_response_appearance("clone", Adw.ResponseAppearance.SUGGESTED)
    confirm.set_default_response("cancel")
    confirm.set_close_response("cancel")
    confirm.connect("response", _on_clone_confirmed, section)
    confirm.present(section._window)


def _on_clone_confirmed(dialog: Adw.AlertDialog, response: str, section) -> None:
    if response != "clone":
        return

    status = clone_repo()
    heading = "Clone Complete" if status.success else "Clone Failed"
    body = status.message
    if status.url:
        body += f"\n\n{status.url}"
    section._alert(heading, body)
    if status.success:
        section.refresh_status()
