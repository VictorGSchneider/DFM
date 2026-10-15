"""Repo init/clone handlers for the GitHub sync section."""

import os

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from dfm.core.github_sync import (
    init_repo, clone_repo, inspect_repo, use_existing_repo, find_existing_repos,
)
from dfm.ui.markup import esc


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


def on_use_existing_clicked(section, _btn: Gtk.Button) -> None:
    """Pick a folder that is already a git clone and use it as the dotfiles repo."""
    dialog = Gtk.FileDialog()
    dialog.set_title("Choose your dotfiles repository")
    suggestions = find_existing_repos()
    start = suggestions[0] if suggestions else os.path.expanduser("~")
    dialog.set_initial_folder(Gio.File.new_for_path(start))
    dialog.select_folder(section._window, None, _on_folder_chosen, section)


def _on_folder_chosen(dialog: Gtk.FileDialog, result, section) -> None:
    try:
        folder = dialog.select_folder_finish(result)
    except GLib.Error:
        return  # cancelled
    path = folder.get_path() if folder is not None else None
    if not path:
        return
    section.run_task(
        "Checking the repository…", lambda: inspect_repo(path),
        lambda status, error: _confirm_existing(section, status, error),
    )


def _confirm_existing(section, status, error) -> None:
    if error is not None:
        section._alert("Couldn't Check the Repository", str(error))
        return
    if not status.success:
        section._alert("Can't Use This Folder", status.message)
        return

    confirm = Adw.AlertDialog()
    confirm.set_heading("Use This Repository?")
    confirm.set_body(
        esc(status.message) + "\n\n" + "\n".join(esc(d) for d in status.details or [])
        + "\n\nPush copies only your enabled dotfiles into it and commits just those. "
          "Pull copies only dotfiles (names starting with a dot) back to your home "
          "folder, with a backup of anything it replaces."
    )
    confirm.set_body_use_markup(True)
    confirm.add_response("cancel", "Cancel")
    confirm.add_response("use", "Use This Repo")
    confirm.set_response_appearance("use", Adw.ResponseAppearance.SUGGESTED)
    confirm.set_default_response("cancel")
    confirm.set_close_response("cancel")
    confirm.connect("response", _on_existing_confirmed, section, status.message)
    confirm.present(section._window)


def _on_existing_confirmed(dialog: Adw.AlertDialog, response: str,
                           section, path: str) -> None:
    if response != "use":
        return
    section.run_task(
        "Linking the repository…", lambda: use_existing_repo(path),
        lambda status, error: _setup_done(
            section, status, error, "Repository Linked", "Couldn't Link"),
    )
