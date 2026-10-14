"""Repo init/clone handlers for the GitHub sync section."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from dfm.core.github_sync import init_repo, clone_repo


def on_init_repo_clicked(section, _btn: Gtk.Button) -> None:
    """Handle create new repo."""
    section.require_auth(lambda: _confirm_init(section))


def _confirm_init(section) -> None:
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

    section.run_task(
        "Creating the repository…", init_repo,
        lambda status, error: _setup_done(
            section, status, error, "Repo Created", "Creation Failed"),
    )


def _setup_done(section, status, error, ok_heading: str, fail_heading: str) -> None:
    if error is not None:
        section._alert(fail_heading, str(error))
        return
    heading = ok_heading if status.success else fail_heading
    body = status.message
    if status.url:
        body += f"\n\n{status.url}"
    section._alert(heading, body)
    if status.success:
        section.refresh_status()


def on_clone_repo_clicked(section, _btn: Gtk.Button) -> None:
    """Handle clone existing repo."""
    section.require_auth(lambda: _confirm_clone(section))


def _confirm_clone(section) -> None:
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

    section.run_task(
        "Cloning the repository…", clone_repo,
        lambda status, error: _setup_done(
            section, status, error, "Clone Complete", "Clone Failed"),
    )
