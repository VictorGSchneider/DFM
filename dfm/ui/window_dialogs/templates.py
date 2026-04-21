"""Browse and install pre-made config templates."""

import os

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from dfm.core.templates import get_templates_by_category, install_template, Template
from dfm.ui.window_dialogs._common import (
    make_dialog, present_dialog, set_dialog_content, StatusMixin,
)


class TemplatesDialog(StatusMixin):
    """Browse and install pre-made config templates."""

    def __init__(self, parent_window, on_rescan_cb=None) -> None:
        self.parent_window = parent_window
        self.on_rescan_cb = on_rescan_cb
        self.dialog = make_dialog("Templates", width=750, height=600)
        self._build_ui()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_title(True)
        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_start(16)
        content_box.set_margin_end(16)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)

        self._status_label = Gtk.Label(label="")
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.add_css_class("dim-label")
        self._status_label.set_visible(False)
        self._status_label.set_wrap(True)
        content_box.append(self._status_label)

        for category, templates in sorted(get_templates_by_category().items()):
            content_box.append(self._build_category_group(category, templates))

        scrolled.set_child(content_box)
        toolbar_view.set_content(scrolled)
        set_dialog_content(self.dialog, toolbar_view)

    def _build_category_group(self, category: str, templates: list[Template]):
        group = Adw.PreferencesGroup()
        group.set_title(category)
        group.set_description(f"{len(templates)} template(s)")
        for template in templates:
            group.add(self._build_template_row(template))
        return group

    def _build_template_row(self, template: Template) -> Adw.ExpanderRow:
        row = Adw.ExpanderRow()
        row.set_title(template.app_name)
        row.set_subtitle(template.description)
        row.set_enable_expansion(True)

        row.add_row(self._build_preview_row(template))
        row.add_row(self._build_dest_row(template))
        return row

    def _build_preview_row(self, template: Template) -> Adw.ActionRow:
        preview_text_view = Gtk.TextView()
        preview_text_view.set_editable(False)
        preview_text_view.set_cursor_visible(False)
        preview_text_view.set_monospace(True)
        preview_text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        lines = template.content.strip().splitlines()
        preview_content = "\n".join(lines[:20])
        if len(lines) > 20:
            preview_content += "\n..."
        preview_text_view.get_buffer().set_text(preview_content)
        preview_text_view.set_left_margin(12)
        preview_text_view.set_right_margin(12)
        preview_text_view.set_top_margin(8)
        preview_text_view.set_bottom_margin(8)

        frame = Gtk.Frame()
        frame.set_child(preview_text_view)
        frame.set_margin_start(12)
        frame.set_margin_end(12)
        frame.set_margin_top(4)
        frame.set_margin_bottom(4)

        preview_action = Adw.ActionRow()
        preview_action.set_child(frame)
        return preview_action

    def _build_dest_row(self, template: Template) -> Adw.ActionRow:
        dest_row = Adw.ActionRow()
        dest_row.set_title("Installs to")
        dest_row.set_subtitle(template.config_path)

        install_btn = Gtk.Button(label="Install")
        install_btn.add_css_class("suggested-action")
        install_btn.set_valign(Gtk.Align.CENTER)
        install_btn._template = template
        install_btn.connect("clicked", self._on_install_clicked)
        dest_row.add_suffix(install_btn)
        return dest_row

    def _on_install_clicked(self, btn: Gtk.Button) -> None:
        template = btn._template
        target = os.path.expanduser(template.config_path)
        if os.path.isfile(target):
            self._confirm_install(template, target)
        else:
            self._do_install(template)

    def _confirm_install(self, template: Template, target: str) -> None:
        confirm_dialog = Adw.AlertDialog()
        confirm_dialog.set_heading("File Exists")
        confirm_dialog.set_body(
            f"The file {target} already exists. "
            f"A backup will be created before overwriting."
        )
        confirm_dialog.add_response("cancel", "Cancel")
        confirm_dialog.add_response("install", "Install Anyway")
        confirm_dialog.set_response_appearance(
            "install", Adw.ResponseAppearance.DESTRUCTIVE,
        )
        confirm_dialog.set_default_response("cancel")
        confirm_dialog.set_close_response("cancel")
        confirm_dialog.connect("response", self._on_confirm_response, template)
        confirm_dialog.present(self.dialog)

    def _on_confirm_response(self, dialog, response: str, template: Template) -> None:
        if response == "install":
            self._do_install(template)

    def _do_install(self, template: Template) -> None:
        try:
            msg = install_template(template, backup=True)
            self._show_status(msg)
            if self.on_rescan_cb is not None:
                self.on_rescan_cb()
        except Exception as e:
            self._show_status(f"Error installing template: {e}")

    def present(self) -> None:
        present_dialog(self.dialog, self.parent_window)
