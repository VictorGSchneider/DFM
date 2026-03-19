import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk, Pango

from dfm.core.scanner import DotfileEntry
from dfm.core.parser import (
    parse_config,
    ConfigField,
    FieldType,
    ParsedConfig,
    update_config_value,
    BOOL_TRUE,
    BOOL_FALSE,
)
from dfm.core.backup import create_backup, get_backups, restore_backup
from dfm.core.validator import validate_file
from dfm.core.dependencies import get_dependencies, get_install_command
from dfm.core.notes import get_note, save_note, DotfileNote, set_favorite
from dfm.ui.window_sidebar import _categorize


def _auto_range(key: str, current_val: float) -> tuple[float, float, float]:
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
    return (0, max(100, current_val * 2), 1)


class ConfigPageBuilder:
    def __init__(self, window):
        self._window = window
        self._debounce_sources: dict[str, int] = {}

    def build(self, entry: DotfileEntry) -> Gtk.Widget:
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vexpand=True,
        )
        clamp = Adw.Clamp(maximum_size=800, margin_start=12, margin_end=12,
                          margin_top=12, margin_bottom=24)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        # Breadcrumbs
        box.append(self._build_breadcrumbs(entry))

        # Title with icon and display name
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                            margin_top=4)
        icon = Gtk.Image.new_from_icon_name("document-properties-symbolic")
        icon.set_pixel_size(32)
        icon.add_css_class("dim-label")
        title_box.append(icon)

        title_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name_label = Gtk.Label(label=entry.display_name, xalign=0)
        name_label.add_css_class("title-1")
        title_inner.append(name_label)

        path_label = Gtk.Label(label=str(entry.path), xalign=0, selectable=True,
                               ellipsize=Pango.EllipsizeMode.MIDDLE)
        path_label.add_css_class("dim-label")
        path_label.add_css_class("caption")
        title_inner.append(path_label)
        title_box.append(title_inner)
        box.append(title_box)

        # Action buttons
        box.append(self._build_actions(entry))

        # Validation
        box.append(self._build_validation(entry))

        # Config fields
        fields_group = Adw.PreferencesGroup(title="Configuration")
        self._populate_fields(fields_group, entry)
        box.append(fields_group)

        # Dependencies
        deps_widget = self._build_deps(entry)
        if deps_widget is not None:
            box.append(deps_widget)

        # Backup history
        box.append(self._build_backup_section(entry))

        # Notes / tags
        box.append(self._build_notes(entry))

        clamp.set_child(box)
        scrolled.set_child(clamp)
        return scrolled

    # ------------------------------------------------------------------
    # Breadcrumbs
    # ------------------------------------------------------------------

    def _build_breadcrumbs(self, entry: DotfileEntry) -> Gtk.Widget:
        category = _categorize(entry)
        crumb_label = Gtk.Label(
            label=f"{category}  >  {entry.display_name}",
            xalign=0,
        )
        crumb_label.add_css_class("dim-label")
        crumb_label.add_css_class("caption")
        return crumb_label

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _build_actions(self, entry: DotfileEntry) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                      margin_top=4, margin_bottom=4)
        box.set_halign(Gtk.Align.START)

        buttons = [
            ("Open in Editor", "text-editor-symbolic", self._on_open_editor),
            ("Open Directory", "folder-open-symbolic", self._on_open_directory),
            ("Export", "document-save-as-symbolic", self._on_export),
            ("View Raw", "utilities-terminal-symbolic", self._on_view_raw),
            ("Share as Gist", "send-to-symbolic", self._on_share_gist),
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
            btn.connect("clicked", callback)
            box.append(btn)

        return box

    def _on_open_editor(self, btn):
        entry = btn._entry
        launcher = Gtk.FileLauncher.new(Gio.File.new_for_path(str(entry.path)))
        launcher.launch(self._window, None, None)

    def _on_open_directory(self, btn):
        entry = btn._entry
        parent = os.path.dirname(entry.path)
        launcher = Gtk.FileLauncher.new(Gio.File.new_for_path(parent))
        launcher.launch(self._window, None, None)

    def _on_export(self, btn):
        entry = btn._entry
        dialog = Gtk.FileDialog()
        dialog.set_initial_name(os.path.basename(entry.path))
        dialog.save(self._window, None, self._on_export_finish, entry)

    def _on_export_finish(self, dialog, result, entry):
        try:
            dest = dialog.save_finish(result)
            if dest:
                import shutil
                shutil.copy2(str(entry.path), dest.get_path())
        except GLib.Error:
            pass

    def _on_view_raw(self, btn):
        entry = btn._entry
        try:
            with open(entry.path, "r", errors="replace") as _f:
                content = _f.read()
        except OSError:
            content = "(unable to read file)"

        dialog = Adw.Dialog()
        dialog.set_title(f"Raw — {entry.display_name}")
        dialog.set_content_width(700)
        dialog.set_content_height(500)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        tv = Gtk.TextView(editable=False, monospace=True,
                          left_margin=12, right_margin=12,
                          top_margin=12, bottom_margin=12)
        tv.get_buffer().set_text(content)
        scrolled.set_child(tv)
        toolbar_view.set_content(scrolled)
        dialog.set_child(toolbar_view)
        dialog.present(self._window)

    def _on_share_gist(self, btn):
        entry = btn._entry
        if hasattr(self._window, "share_as_gist"):
            self._window.share_as_gist(entry)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _build_validation(self, entry: DotfileEntry) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_halign(Gtk.Align.START)

        config_path = entry.get_config_path()
        result = validate_file(config_path or entry.path)

        errors = getattr(result, "errors", [])
        warnings = getattr(result, "warnings", [])

        if not errors and not warnings:
            badge = Gtk.Label(label="Valid")
            badge.add_css_class("success")
            badge.add_css_class("caption")
            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            icon.add_css_class("success")
            box.append(icon)
            box.append(badge)
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

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def _build_deps(self, entry: DotfileEntry) -> Gtk.Widget | None:
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
            copy_btn.connect("clicked", self._on_copy_dep_cmd)
            cmd_row.add_suffix(copy_btn)
            group.add(cmd_row)

        return group

    def _on_copy_dep_cmd(self, btn):
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(btn._cmd)

    # ------------------------------------------------------------------
    # Notes / Tags
    # ------------------------------------------------------------------

    def _build_notes(self, entry: DotfileEntry) -> Gtk.Widget:
        group = Adw.PreferencesGroup(title="Notes & Tags")

        note = get_note(entry.name)
        note_text = note.note if note else ""
        tags = list(note.tags) if note else []
        is_fav = note.favorite if note else False

        # Favorite toggle
        fav_row = Adw.ActionRow(title="Favorite")
        fav_btn = Gtk.ToggleButton(
            icon_name="starred-symbolic" if is_fav else "non-starred-symbolic",
            valign=Gtk.Align.CENTER,
            active=is_fav,
        )
        fav_btn.add_css_class("flat")
        fav_btn._entry = entry
        fav_btn.connect("toggled", self._on_fav_toggled)
        fav_row.add_suffix(fav_btn)
        group.add(fav_row)

        # Notes text area
        notes_row = Adw.ActionRow(title="Notes")
        notes_row.set_size_request(-1, 100)

        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            min_content_height=80,
            max_content_height=160,
            valign=Gtk.Align.CENTER,
        )
        tv = Gtk.TextView(
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            top_margin=6,
            bottom_margin=6,
            left_margin=6,
            right_margin=6,
            hexpand=True,
        )
        tv.get_buffer().set_text(note_text)
        tv.get_buffer()._entry = entry
        tv.get_buffer().connect("changed", self._on_note_text_changed)
        scrolled.set_child(tv)
        notes_row.add_suffix(scrolled)
        group.add(notes_row)

        # Tags
        tags_row = Adw.ActionRow(title="Tags")
        tags_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6,
                           valign=Gtk.Align.CENTER)

        tag_entry = Gtk.Entry(
            placeholder_text="comma separated",
            hexpand=True,
            valign=Gtk.Align.CENTER,
        )
        tag_entry.set_text(", ".join(tags))
        tags_box.append(tag_entry)

        add_btn = Gtk.Button(label="Save Tags", valign=Gtk.Align.CENTER)
        add_btn.add_css_class("flat")
        add_btn._entry = entry
        add_btn._tag_entry = tag_entry
        add_btn.connect("clicked", self._on_save_tags)
        tags_box.append(add_btn)

        tags_row.add_suffix(tags_box)
        group.add(tags_row)

        return group

    def _on_fav_toggled(self, btn):
        entry = btn._entry
        active = btn.get_active()
        btn.set_icon_name("starred-symbolic" if active else "non-starred-symbolic")
        set_favorite(entry.name, active)

    def _on_note_text_changed(self, buf):
        entry = buf._entry
        key = f"note-{entry.path}"
        if key in self._debounce_sources:
            GLib.source_remove(self._debounce_sources[key])

        def _save():
            start = buf.get_start_iter()
            end = buf.get_end_iter()
            text = buf.get_text(start, end, False)
            note = get_note(entry.name)
            tags = list(note.tags)
            fav = note.favorite
            save_note(DotfileNote(name=entry.name, note=text, tags=tags, favorite=fav))
            self._debounce_sources.pop(key, None)
            return False

        self._debounce_sources[key] = GLib.timeout_add(500, _save)

    def _on_save_tags(self, btn):
        entry = btn._entry
        raw = btn._tag_entry.get_text()
        tags = [t.strip() for t in raw.split(",") if t.strip()]
        note = get_note(entry.name)
        text = note.note
        fav = note.favorite
        save_note(DotfileNote(name=entry.name, note=text, tags=tags, favorite=fav))

    # ------------------------------------------------------------------
    # Backup history
    # ------------------------------------------------------------------

    def _build_backup_section(self, entry: DotfileEntry) -> Gtk.Widget:
        group = Adw.PreferencesGroup(title="Backup History")

        config_path = entry.get_config_path() or entry.path
        backups = get_backups(config_path)
        if not backups:
            row = Adw.ActionRow(title="No backups yet")
            row.add_css_class("dim-label")
            group.add(row)
            return group

        for backup in backups[:5]:
            label = backup.display_time
            reason = getattr(backup, "reason", "")

            size_str = ""
            if backup.size > 0:
                if backup.size < 1024:
                    size_str = f"{backup.size} B"
                elif backup.size < 1024 * 1024:
                    size_str = f"{backup.size / 1024:.1f} KB"
                else:
                    size_str = f"{backup.size / (1024 * 1024):.1f} MB"

            subtitle = f"{size_str} · {reason}" if reason else size_str
            row = Adw.ActionRow(title=label, subtitle=subtitle)

            restore_btn = Gtk.Button(label="Restore", valign=Gtk.Align.CENTER)
            restore_btn.add_css_class("flat")
            restore_btn._backup = backup
            restore_btn._entry = entry
            restore_btn._group = group
            restore_btn.connect("clicked", self._on_restore_backup)
            row.add_suffix(restore_btn)
            group.add(row)

        return group

    def _on_restore_backup(self, btn):
        backup = btn._backup
        entry = btn._entry
        restore_backup(backup)
        toast = Adw.Toast.new(f"Restored backup for {entry.display_name}")
        if hasattr(self._window, "_toast_overlay"):
            self._window._toast_overlay.add_toast(toast)

    # ------------------------------------------------------------------
    # Config fields
    # ------------------------------------------------------------------

    def _populate_fields(self, container, entry: DotfileEntry):
        parsed = parse_config(entry.path)
        if parsed is None:
            row = Adw.ActionRow(title="Unable to parse configuration file")
            row.add_css_class("dim-label")
            container.add(row)
            return

        fields = getattr(parsed, "fields", [])
        if not fields:
            row = Adw.ActionRow(title="No configurable fields detected")
            row.add_css_class("dim-label")
            container.add(row)
            return

        for field in fields:
            row = self._create_field_row(field, parsed, entry)
            if row is not None:
                container.add(row)

    def _create_field_row(self, field: ConfigField, parsed: ParsedConfig,
                          entry: DotfileEntry) -> Adw.ActionRow | None:
        ftype = field.field_type if hasattr(field, "field_type") else getattr(field, "type", None)
        key = field.key
        value = field.value
        description = getattr(field, "description", "") or ""

        # TOGGLE
        if ftype == FieldType.TOGGLE:
            row = Adw.SwitchRow(title=key, subtitle=description)
            is_on = str(value).lower() in [v.lower() for v in BOOL_TRUE]
            row.set_active(is_on)
            row._field = field
            row._parsed = parsed
            row._entry = entry
            row.connect("notify::active", self._on_toggle_changed)
            return row

        # SLIDER
        if ftype == FieldType.SLIDER:
            row = Adw.ActionRow(title=key, subtitle=description)
            try:
                current = float(value)
            except (TypeError, ValueError):
                current = 0.0
            lo, hi, step = _auto_range(key, current)
            adj = Gtk.Adjustment(value=current, lower=lo, upper=hi,
                                 step_increment=step, page_increment=step * 10)
            scale = Gtk.Scale(
                orientation=Gtk.Orientation.HORIZONTAL,
                adjustment=adj,
                draw_value=True,
                digits=2 if step < 1 else 0,
                hexpand=True,
                valign=Gtk.Align.CENTER,
            )
            scale.set_size_request(200, -1)
            scale._field = field
            scale._parsed = parsed
            scale._entry = entry
            scale.connect("value-changed", self._on_scale_changed)
            row.add_suffix(scale)
            return row

        # COLOR
        if ftype == FieldType.COLOR:
            row = Adw.ActionRow(title=key, subtitle=description)
            rgba = Gdk.RGBA()
            color_str = str(value) if value else "#000000"
            if not rgba.parse(color_str):
                rgba.parse("#000000")
            color_dialog = Gtk.ColorDialog()
            color_btn = Gtk.ColorDialogButton(dialog=color_dialog,
                                              valign=Gtk.Align.CENTER)
            color_btn.set_rgba(rgba)
            color_btn._field = field
            color_btn._parsed = parsed
            color_btn._entry = entry
            color_btn.connect("notify::rgba", self._on_color_changed)
            row.add_suffix(color_btn)
            return row

        # NUMBER
        if ftype == FieldType.NUMBER:
            row = Adw.ActionRow(title=key, subtitle=description)
            try:
                current = float(value)
            except (TypeError, ValueError):
                current = 0.0
            lo, hi, step = _auto_range(key, current)
            adj = Gtk.Adjustment(value=current, lower=lo, upper=hi,
                                 step_increment=step, page_increment=step * 10)
            spin = Gtk.SpinButton(adjustment=adj, climb_rate=1,
                                  digits=2 if step < 1 else 0,
                                  valign=Gtk.Align.CENTER)
            spin._field = field
            spin._parsed = parsed
            spin._entry = entry
            spin.connect("value-changed", self._on_spin_changed)
            row.add_suffix(spin)
            return row

        # PATH
        if ftype == FieldType.PATH:
            row = Adw.ActionRow(title=key, subtitle=description)
            path_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4,
                               valign=Gtk.Align.CENTER)
            path_entry = Gtk.Entry(text=str(value) if value else "",
                                   hexpand=True, valign=Gtk.Align.CENTER)
            path_entry.set_size_request(200, -1)
            path_entry._field = field
            path_entry._parsed = parsed
            path_entry._entry = entry
            path_entry.connect("changed", self._on_text_field_changed)
            path_box.append(path_entry)

            browse_btn = Gtk.Button(icon_name="folder-open-symbolic",
                                    valign=Gtk.Align.CENTER,
                                    tooltip_text="Browse")
            browse_btn.add_css_class("flat")
            browse_btn._path_entry = path_entry
            browse_btn.connect("clicked", self._on_browse_path)
            path_box.append(browse_btn)
            row.add_suffix(path_box)
            return row

        # KEYBIND
        if ftype == FieldType.KEYBIND:
            row = Adw.ActionRow(title=key, subtitle=description)
            label = Gtk.Label(label=str(value) if value else "",
                              selectable=True, valign=Gtk.Align.CENTER)
            label.add_css_class("monospace")
            row.add_suffix(label)
            return row

        # FONT
        if ftype == FieldType.FONT:
            row = Adw.ActionRow(title=key, subtitle=description)
            font_entry = Gtk.Entry(text=str(value) if value else "",
                                   valign=Gtk.Align.CENTER)
            font_entry.set_size_request(200, -1)
            font_entry._field = field
            font_entry._parsed = parsed
            font_entry._entry = entry
            font_entry.connect("changed", self._on_text_field_changed)
            row.add_suffix(font_entry)
            return row

        # Default — text entry
        row = Adw.ActionRow(title=key, subtitle=description)
        text_entry = Gtk.Entry(text=str(value) if value else "",
                               valign=Gtk.Align.CENTER, hexpand=True)
        text_entry.set_size_request(200, -1)
        text_entry._field = field
        text_entry._parsed = parsed
        text_entry._entry = entry
        text_entry.connect("changed", self._on_text_field_changed)
        row.add_suffix(text_entry)
        return row

    # ------------------------------------------------------------------
    # Field change handlers
    # ------------------------------------------------------------------

    def _on_toggle_changed(self, row, _pspec):
        field = row._field
        entry = row._entry
        parsed = row._parsed
        new_val = BOOL_TRUE[0] if row.get_active() else BOOL_FALSE[0]
        create_backup(str(entry.path), "edit")
        update_config_value(entry.path, parsed, field, new_val)

    def _on_scale_changed(self, scale):
        field = scale._field
        entry = scale._entry
        parsed = scale._parsed
        new_val = str(scale.get_value())
        key = f"scale-{id(scale)}"
        if key in self._debounce_sources:
            GLib.source_remove(self._debounce_sources[key])

        def _save():
            create_backup(str(entry.path), "edit")
            update_config_value(entry.path, parsed, field, new_val)
            self._debounce_sources.pop(key, None)
            return False

        self._debounce_sources[key] = GLib.timeout_add(500, _save)

    def _on_color_changed(self, btn, _pspec):
        field = btn._field
        entry = btn._entry
        parsed = btn._parsed
        rgba = btn.get_rgba()
        hex_color = "#{:02x}{:02x}{:02x}".format(
            int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)
        )
        create_backup(str(entry.path), "edit")
        update_config_value(entry.path, parsed, field, hex_color)

    def _on_spin_changed(self, spin):
        field = spin._field
        entry = spin._entry
        parsed = spin._parsed
        new_val = str(spin.get_value())
        key = f"spin-{id(spin)}"
        if key in self._debounce_sources:
            GLib.source_remove(self._debounce_sources[key])

        def _save():
            create_backup(str(entry.path), "edit")
            update_config_value(entry.path, parsed, field, new_val)
            self._debounce_sources.pop(key, None)
            return False

        self._debounce_sources[key] = GLib.timeout_add(500, _save)

    def _on_text_field_changed(self, widget):
        field = widget._field
        entry = widget._entry
        parsed = widget._parsed
        new_val = widget.get_text()
        key = f"text-{id(widget)}"
        if key in self._debounce_sources:
            GLib.source_remove(self._debounce_sources[key])

        def _save():
            create_backup(str(entry.path), "edit")
            update_config_value(entry.path, parsed, field, new_val)
            self._debounce_sources.pop(key, None)
            return False

        self._debounce_sources[key] = GLib.timeout_add(500, _save)

    def _on_browse_path(self, btn):
        path_entry = btn._path_entry
        dialog = Gtk.FileDialog()
        current = path_entry.get_text()
        if current and os.path.exists(current):
            dialog.set_initial_file(Gio.File.new_for_path(current))
        dialog.open(self._window, None, self._on_browse_finish, path_entry)

    def _on_browse_finish(self, dialog, result, path_entry):
        try:
            f = dialog.open_finish(result)
            if f:
                path_entry.set_text(f.get_path())
        except GLib.Error:
            pass
