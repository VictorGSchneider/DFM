"""DFM - Dotfile Manager for Arch Linux.

A GTK4/Adwaita GUI application for managing dotfiles.
"""

import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio

from dfm.window import DfmWindow


CSS = """
.sidebar {
    background-color: alpha(@window_bg_color, 0.97);
    border-right: 1px solid alpha(@borders, 0.5);
}

.navigation-sidebar row {
    border-radius: 8px;
    margin: 2px 6px;
    padding: 4px 0;
}

.navigation-sidebar row:selected {
    background-color: alpha(@accent_bg_color, 0.15);
    color: @accent_fg_color;
}

.title-1 {
    font-weight: 800;
    font-size: 1.4em;
}

.dim-label {
    opacity: 0.55;
}

.keybind-label {
    font-family: monospace;
    padding: 2px 8px;
    border-radius: 4px;
    background-color: alpha(@card_bg_color, 0.7);
}

.monospace {
    font-family: monospace;
    font-size: 0.9em;
}

.warning {
    color: @warning_color;
}
"""


class DfmApplication(Adw.Application):
    """Main application class."""

    def __init__(self) -> None:
        super().__init__(
            application_id="com.github.dfm",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)

        # Load CSS
        from gi.repository import Gdk
        css_provider = Gtk.CssProvider()
        css_provider.load_from_string(CSS)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def do_activate(self) -> None:
        win = self.props.active_window
        if not win:
            win = DfmWindow(self)
        win.present()


def main() -> None:
    """Entry point."""
    app = DfmApplication()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
