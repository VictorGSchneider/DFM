"""Generate base configs for installed apps that lack config files."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from dfm.core.wizard import get_available_wizards, run_wizard, WizardApp
from dfm.ui.window_dialogs._common import (
    make_dialog, present_dialog, set_dialog_content, StatusMixin,
)


class WizardDialog(StatusMixin):
    """Generate base configs for installed apps that lack config files."""

    def __init__(self, parent_window, dotfiles: list, on_rescan_cb=None) -> None:
        self.parent_window = parent_window
        self.dotfiles = dotfiles
        self.on_rescan_cb = on_rescan_cb
        self.dialog = make_dialog("Config Wizard", width=650, height=500)
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

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._content_box.set_margin_start(16)
        self._content_box.set_margin_end(16)
        self._content_box.set_margin_top(12)
        self._content_box.set_margin_bottom(12)

        self._status_label = Gtk.Label(label="")
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.add_css_class("dim-label")
        self._status_label.set_visible(False)
        self._status_label.set_wrap(True)
        self._content_box.append(self._status_label)

        wizards = get_available_wizards(self.dotfiles)
        if not wizards:
            empty = Adw.PreferencesGroup()
            empty.set_title("No Suggestions")
            empty.set_description(
                "All installed applications already have config files, "
                "or no supported applications were detected."
            )
            self._content_box.append(empty)
        else:
            self._build_wizard_groups(wizards)

        scrolled.set_child(self._content_box)
        toolbar_view.set_content(scrolled)
        set_dialog_content(self.dialog, toolbar_view)

    def _build_wizard_groups(self, wizards: list[WizardApp]) -> None:
        categories: dict[str, list[WizardApp]] = {}
        for app in wizards:
            categories.setdefault(app.category, []).append(app)

        desc_group = Adw.PreferencesGroup()
        desc_group.set_title("Available Configs")
        desc_group.set_description(
            f"{len(wizards)} installed app(s) detected without config files"
        )
        self._content_box.append(desc_group)

        for category, apps in sorted(categories.items()):
            group = Adw.PreferencesGroup()
            group.set_title(category)
            for app in apps:
                group.add(self._build_app_row(app))
            self._content_box.append(group)

    def _build_app_row(self, app: WizardApp) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_title(app.display_name)
        row.set_subtitle(f"{app.description} | {app.config_path}")

        generate_btn = Gtk.Button(label="Generate")
        generate_btn.add_css_class("suggested-action")
        generate_btn.set_valign(Gtk.Align.CENTER)
        generate_btn._wizard_app = app
        generate_btn.connect("clicked", self._on_generate_clicked)
        row.add_suffix(generate_btn)
        return row

    def _on_generate_clicked(self, btn: Gtk.Button) -> None:
        app = btn._wizard_app
        try:
            msg = run_wizard(app)
            self._show_status(msg)
            btn.set_sensitive(False)
            btn.set_label("Done")
            if self.on_rescan_cb is not None:
                self.on_rescan_cb()
        except Exception as e:
            self._show_status(f"Error generating config: {e}")

    def present(self) -> None:
        present_dialog(self.dialog, self.parent_window)
