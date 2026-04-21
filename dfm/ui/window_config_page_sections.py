"""Non-field sections of the config page: actions, validation, notes, backups."""

import os
import sys
import shutil

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk

from dfm.core.scanner import DotfileEntry
from dfm.core.backup import get_backups, restore_backup
from dfm.core.validator import validate_file
from dfm.core.dependencies import get_dependencies, get_install_command
from dfm.core.notes import get_note, save_note, DotfileNote, set_favorite


# ── Actions row ───────────────────────────────────────────────────────


def build_actions(builder, entry: DotfileEntry) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                  margin_top=4, margin_bottom=4)
    box.set_halign(Gtk.Align.START)

    buttons = [
        ("Open in Editor", "text-editor-symbolic", _on_open_editor),
        ("Open Directory", "folder-open-symbolic", _on_open_directory),
        ("Export", "document-save-as-symbolic", _on_export),
        ("View Raw", "utilities-terminal-symbolic", _on_view_raw),
        ("Share as Gist", "send-to-symbolic", _on_share_gist),
    ]

    for tooltip, icon_name, callback in buttons:
        btn = Gtk.Button(tooltip_text=tooltip)
        if tooltip in ("Open in Editor", "Export"):
            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            btn_box.append(Gtk.Image.new_from_icon_name(icon_name))
            btn_box.append(Gtk.Label(label=tooltip))
            btn.set_child(btn_box)
        else:
            btn.set_child(Gtk.Image.new_from_icon_name(icon_name))
        btn.add_css_class("flat")
        btn._entry = entry
        btn._builder = builder
        btn.connect("clicked", callback)
        box.append(btn)

    return box


def _on_open_editor(btn):
    entry = btn._entry
    config_path = entry.get_config_path() or entry.path
    launcher = Gtk.FileLauncher.new(Gio.File.new_for_path(str(config_path)))
    launcher.launch(btn._builder._window, None, None)


def _on_open_directory(btn):
    entry = btn._entry
    parent = entry.path if entry.is_directory else os.path.dirname(entry.path)
    launcher = Gtk.FileLauncher.new(Gio.File.new_for_path(parent))
    launcher.launch(btn._builder._window, None, None)


def _on_export(btn):
    entry = btn._entry
    config_path = entry.get_config_path() or entry.path
    dialog = Gtk.FileDialog()
    dialog.set_initial_name(os.path.basename(config_path))
    dialog.save(btn._builder._window, None, _on_export_finish, entry)


def _on_export_finish(dialog, result, entry):
    try:
        dest = dialog.save_finish(result)
        if dest:
            config_path = entry.get_config_path() or entry.path
            shutil.copy2(str(config_path), dest.get_path())
    except GLib.Error as e:
        if e.code != 2:
            print(f"DFM export error: {e}", file=sys.stderr)


def _on_view_raw(btn):
    entry = btn._entry
    config_path = entry.get_config_path() or entry.path
    try:
        with open(config_path, "r", errors="replace") as f:
            content = f.read()
    except OSError:
        content = "(unable to read file)"

    dialog = Adw.Dialog()
    dialog.set_title(f"Raw — {entry.display_name}")
    dialog.set_content_width(700)
    dialog.set_content_height(500)

    toolbar_view = Adw.ToolbarView()
    toolbar_view.add_top_bar(Adw.HeaderBar())

    scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
    tv = Gtk.TextView(editable=False, monospace=True,
                      left_margin=12, right_margin=12,
                      top_margin=12, bottom_margin=12)
    tv.get_buffer().set_text(content)
    scrolled.set_child(tv)
    toolbar_view.set_content(scrolled)
    dialog.set_child(toolbar_view)
    dialog.present(btn._builder._window)


def _on_share_gist(btn):
    window = btn._builder._window
    if hasattr(window, "share_as_gist"):
        window.share_as_gist(btn._entry)


# ── Validation ────────────────────────────────────────────────────────


def build_validation(entry: DotfileEntry) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    box.set_halign(Gtk.Align.START)

    result = validate_file(entry.get_config_path() or entry.path)
    errors = getattr(result, "errors", [])
    warnings = getattr(result, "warnings", [])

    if not errors and not warnings:
        badge = Gtk.Label(label="Valid")
        badge.add_css_class("success")
        badge.add_css_class("caption")
        icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        icon.add_css_class("success")
    else:
        parts = []
        if errors:
            parts.append(f"{len(errors)} error{'s' if len(errors) != 1 else ''}")
        if warnings:
            parts.append(f"{len(warnings)} warning{'s' if len(warnings) != 1 else ''}")
        badge = Gtk.Label(label=", ".join(parts))
        badge.add_css_class("caption")
        if errors:
            badge.add_css_class("error")
            icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
            icon.add_css_class("error")
        else:
            badge.add_css_class("warning")
            icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            icon.add_css_class("warning")

    box.append(icon)
    box.append(badge)
    return box


# ── Dependencies ─────────────────────────────────────────────────────


def build_deps(entry: DotfileEntry) -> Gtk.Widget | None:
    deps = get_dependencies(entry)
    if not deps:
        return None

    group = Adw.PreferencesGroup(title="Dependencies")

    for dep in deps:
        row = Adw.ActionRow()
        row.set_title(dep.package)
        row.set_subtitle(dep.description)
        if dep.installed:
            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            icon.add_css_class("success")
        else:
            icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            icon.add_css_class("warning")
        icon.set_valign(Gtk.Align.CENTER)
        row.add_suffix(icon)
        group.add(row)

    cmd = get_install_command(deps, only_missing=True)
    if cmd:
        cmd_row = Adw.ActionRow()
        cmd_row.set_title("Install missing")
        cmd_row.set_subtitle(cmd)
        copy_btn = Gtk.Button(icon_name="edit-copy-symbolic",
                              valign=Gtk.Align.CENTER,
                              tooltip_text="Copy command")
        copy_btn.add_css_class("flat")
        copy_btn._cmd = cmd
        copy_btn.connect(
            "clicked",
            lambda b: Gdk.Display.get_default().get_clipboard().set(b._cmd),
        )
        cmd_row.add_suffix(copy_btn)
        group.add(cmd_row)

    return group


# ── Notes / Tags ─────────────────────────────────────────────────────


def build_notes(builder, entry: DotfileEntry) -> Gtk.Widget:
    group = Adw.PreferencesGroup(title="Notes & Tags")

    note = get_note(entry.name)
    note_text = note.note if note else ""
    tags = list(note.tags) if note else []
    is_fav = note.favorite if note else False

    fav_row = Adw.ActionRow(title="Favorite")
    fav_btn = Gtk.ToggleButton(
        icon_name="starred-symbolic" if is_fav else "non-starred-symbolic",
        valign=Gtk.Align.CENTER, active=is_fav,
    )
    fav_btn.add_css_class("flat")
    fav_btn._entry = entry
    fav_btn.connect("toggled", _on_fav_toggled)
    fav_row.add_suffix(fav_btn)
    group.add(fav_row)

    notes_row = Adw.ActionRow(title="Notes")
    notes_row.set_size_request(-1, 100)

    scrolled = Gtk.ScrolledWindow(
        hscrollbar_policy=Gtk.PolicyType.NEVER,
        min_content_height=80, max_content_height=160,
        valign=Gtk.Align.CENTER,
    )
    tv = Gtk.TextView(
        wrap_mode=Gtk.WrapMode.WORD_CHAR,
        top_margin=6, bottom_margin=6, left_margin=6, right_margin=6,
        hexpand=True,
    )
    tv.get_buffer().set_text(note_text)
    tv.get_buffer()._entry = entry
    tv.get_buffer()._builder = builder
    tv.get_buffer().connect("changed", _on_note_text_changed)
    scrolled.set_child(tv)
    notes_row.add_suffix(scrolled)
    group.add(notes_row)

    tags_row = Adw.ActionRow(title="Tags")
    tags_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                       valign=Gtk.Align.CENTER)

    tag_entry = Gtk.Entry(
        placeholder_text="comma separated",
        hexpand=True, valign=Gtk.Align.CENTER,
    )
    tag_entry.set_text(", ".join(tags))
    tags_box.append(tag_entry)

    add_btn = Gtk.Button(label="Save Tags", valign=Gtk.Align.CENTER)
    add_btn.add_css_class("flat")
    add_btn._entry = entry
    add_btn._tag_entry = tag_entry
    add_btn.connect("clicked", _on_save_tags)
    tags_box.append(add_btn)

    tags_row.add_suffix(tags_box)
    group.add(tags_row)

    return group


def _on_fav_toggled(btn):
    entry = btn._entry
    active = btn.get_active()
    btn.set_icon_name("starred-symbolic" if active else "non-starred-symbolic")
    set_favorite(entry.name, active)


def _on_note_text_changed(buf):
    entry = buf._entry
    builder = buf._builder
    key = f"note-{entry.path}"
    if key in builder._debounce_sources:
        GLib.source_remove(builder._debounce_sources[key])

    def _save():
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        text = buf.get_text(start, end, False)
        note = get_note(entry.name)
        save_note(DotfileNote(name=entry.name, note=text,
                              tags=list(note.tags), favorite=note.favorite))
        builder._debounce_sources.pop(key, None)
        return False

    builder._debounce_sources[key] = GLib.timeout_add(500, _save)


def _on_save_tags(btn):
    entry = btn._entry
    raw = btn._tag_entry.get_text()
    tags = [t.strip() for t in raw.split(",") if t.strip()]
    note = get_note(entry.name)
    save_note(DotfileNote(name=entry.name, note=note.note,
                          tags=tags, favorite=note.favorite))


# ── Backup history ───────────────────────────────────────────────────


def build_backup_section(builder, entry: DotfileEntry) -> Gtk.Widget:
    group = Adw.PreferencesGroup(title="Backup History")

    config_path = entry.get_config_path() or entry.path
    backups = get_backups(config_path)
    if not backups:
        row = Adw.ActionRow(title="No backups yet")
        row.add_css_class("dim-label")
        group.add(row)
        return group

    for backup in backups[:5]:
        subtitle_parts = []
        if backup.size > 0:
            if backup.size < 1024:
                subtitle_parts.append(f"{backup.size} B")
            elif backup.size < 1024 * 1024:
                subtitle_parts.append(f"{backup.size / 1024:.1f} KB")
            else:
                subtitle_parts.append(f"{backup.size / (1024 * 1024):.1f} MB")

        reason = getattr(backup, "reason", "")
        if reason:
            subtitle_parts.append(reason)

        row = Adw.ActionRow(title=backup.display_time,
                            subtitle=" · ".join(subtitle_parts))

        restore_btn = Gtk.Button(label="Restore", valign=Gtk.Align.CENTER)
        restore_btn.add_css_class("flat")
        restore_btn._backup = backup
        restore_btn._entry = entry
        restore_btn._builder = builder
        restore_btn.connect("clicked", _on_restore_backup)
        row.add_suffix(restore_btn)
        group.add(row)

    return group


def _on_restore_backup(btn):
    backup = btn._backup
    entry = btn._entry
    builder = btn._builder
    confirm = Adw.AlertDialog()
    confirm.set_heading("Restore Backup?")
    confirm.set_body(
        f"Restore {entry.display_name} from backup dated "
        f"{backup.display_time}?\n\n"
        f"The current file will be backed up before restoring."
    )
    confirm.add_response("cancel", "Cancel")
    confirm.add_response("restore", "Restore")
    confirm.set_response_appearance("restore", Adw.ResponseAppearance.DESTRUCTIVE)
    confirm.set_default_response("cancel")
    confirm.set_close_response("cancel")
    confirm.connect("response", _on_restore_confirmed, backup, entry, builder)
    confirm.present(builder._window)


def _on_restore_confirmed(dialog, response, backup, entry, builder):
    if response != "restore":
        return
    restore_backup(backup)
    config_path = entry.get_config_path() or entry.path
    monitor = getattr(builder._window, "_monitor", None)
    if monitor is not None:
        monitor.update_state(str(config_path))
    toast = Adw.Toast.new(f"Restored backup for {entry.display_name}")
    if hasattr(builder._window, "_toast_overlay"):
        builder._window._toast_overlay.add_toast(toast)
