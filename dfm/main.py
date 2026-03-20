"""DFM - Dotfile Manager for Arch Linux.

A GTK4/Adwaita GUI application for managing dotfiles.
"""

import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio

from dfm.ui.window import DfmWindow


CSS = """
/* ╔══════════════════════════════════════════════════════════════╗
   ║  STOA LINUX — DFM Theme                                     ║
   ║  Roman marble, bronze, parchment, and stone.                 ║
   ╚══════════════════════════════════════════════════════════════╝ */

/* ── Stoa Palette (Libadwaita overrides) ── */
@define-color stoa_bg_dark     #1a1714;
@define-color stoa_bg          #211e19;
@define-color stoa_bg_light    #2d2921;
@define-color stoa_fg          #d4cfc4;
@define-color stoa_fg_dim      #a89f91;
@define-color stoa_fg_dark     #7a7267;
@define-color stoa_bronze      #c49a5c;
@define-color stoa_gold        #d4a84b;
@define-color stoa_parchment   #c4b08a;
@define-color stoa_olive       #8a9a6c;
@define-color stoa_laurel      #6b7f52;
@define-color stoa_terracotta  #b36b5a;
@define-color stoa_azure       #5a7a8a;
@define-color stoa_stone       #6e6a62;
@define-color stoa_marble      #9e9a92;

@define-color accent_bg_color        @stoa_bronze;
@define-color accent_fg_color        @stoa_bg_dark;
@define-color accent_color           @stoa_bronze;
@define-color window_bg_color        @stoa_bg;
@define-color window_fg_color        @stoa_fg;
@define-color view_bg_color          @stoa_bg_dark;
@define-color view_fg_color          @stoa_fg;
@define-color headerbar_bg_color     @stoa_bg_dark;
@define-color headerbar_fg_color     @stoa_fg;
@define-color headerbar_backdrop_color @stoa_bg_dark;
@define-color sidebar_bg_color       @stoa_bg_dark;
@define-color sidebar_fg_color       @stoa_fg;
@define-color sidebar_backdrop_color @stoa_bg_dark;
@define-color card_bg_color          @stoa_bg_light;
@define-color card_fg_color          @stoa_fg;
@define-color popover_bg_color       @stoa_bg_light;
@define-color popover_fg_color       @stoa_fg;
@define-color dialog_bg_color        @stoa_bg;
@define-color dialog_fg_color        @stoa_fg;
@define-color shade_color            rgba(0, 0, 0, 0.36);
@define-color scrollbar_outline_color rgba(0, 0, 0, 0.5);
@define-color error_bg_color         @stoa_terracotta;
@define-color error_fg_color         @stoa_fg;
@define-color error_color            @stoa_terracotta;
@define-color warning_bg_color       @stoa_gold;
@define-color warning_fg_color       @stoa_bg_dark;
@define-color warning_color          @stoa_gold;
@define-color success_bg_color       @stoa_olive;
@define-color success_fg_color       @stoa_bg_dark;
@define-color success_color          @stoa_olive;
@define-color destructive_bg_color   @stoa_terracotta;
@define-color destructive_fg_color   @stoa_fg;
@define-color destructive_color      @stoa_terracotta;

/* ── Scrollbar ── */
scrollbar slider {
    background-color: @stoa_stone;
    border-radius: 3px;
}
scrollbar slider:hover {
    background-color: @stoa_marble;
}

/* ── Selection ── */
*:selected, selection {
    background-color: @stoa_bronze;
    color: @stoa_bg_dark;
}

/* ── Switch ── */
switch:checked {
    background-color: @stoa_olive;
}

/* ── Progress / Scale ── */
progressbar > trough > progress {
    background-color: @stoa_bronze;
}
scale > trough > highlight {
    background-color: @stoa_bronze;
}

/* ── Separator ── */
separator {
    background-color: @stoa_stone;
}

/* ── Sidebar ── */
.sidebar {
    background-color: @stoa_bg_dark;
    border-right: 1px solid @stoa_stone;
}

.navigation-sidebar row {
    border-radius: 4px;
    margin: 2px 6px;
    padding: 2px 0;
    min-height: 32px;
}

.navigation-sidebar row:selected {
    background-color: @stoa_bronze;
    color: @stoa_bg_dark;
}

/* ── Typography ── */
.caption-heading {
    font-weight: 700;
    font-size: 0.85em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: @stoa_bronze;
}

.title-1 {
    font-weight: 800;
    font-size: 1.4em;
    color: @stoa_fg;
}

.dim-label {
    opacity: 0.55;
    color: @stoa_fg_dim;
}

.heading {
    color: @stoa_parchment;
}

/* ── Code / Keybinds ── */
.keybind-label {
    font-family: monospace;
    padding: 2px 8px;
    border-radius: 4px;
    background-color: @stoa_bg_light;
    color: @stoa_parchment;
}

.monospace {
    font-family: monospace;
    font-size: 0.9em;
}

/* ── Status badges ── */
.warning {
    color: @stoa_gold;
}

.breadcrumb {
    font-size: 0.85em;
    color: @stoa_fg_dark;
}

.diff-add {
    color: @stoa_olive;
}

.diff-del {
    color: @stoa_terracotta;
}

.diff-header {
    color: @stoa_azure;
    font-weight: bold;
}

.conflict-warning {
    background-color: alpha(@stoa_gold, 0.1);
    border-radius: 4px;
    border-left: 3px solid @stoa_gold;
    padding: 8px;
}

.tag-chip {
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 0.85em;
    background-color: alpha(@stoa_bronze, 0.15);
    color: @stoa_bronze;
}

.favorite-star {
    color: @stoa_gold;
}

.badge-valid {
    color: @stoa_olive;
    font-weight: bold;
    font-size: 0.85em;
}

.badge-warning {
    color: @stoa_gold;
    font-weight: bold;
    font-size: 0.85em;
}

.badge-error {
    color: @stoa_terracotta;
    font-weight: bold;
    font-size: 0.85em;
}

.search-entry {
    margin: 4px 8px;
}

.monitor-bar {
    background-color: alpha(@stoa_gold, 0.15);
    padding: 6px 12px;
    border-bottom: 1px solid alpha(@stoa_gold, 0.3);
}

/* ── Analyzer ── */
.analyzer-card {
    background-color: @stoa_bg_light;
    border-radius: 8px;
    padding: 12px 20px;
    min-width: 80px;
}

.analyzer-card-value {
    font-size: 1.6em;
    font-weight: 800;
}

.analyzer-error {
    color: @stoa_terracotta;
}

.analyzer-warning {
    color: @stoa_gold;
}

.analyzer-info {
    color: @stoa_azure;
}

.analyzer-ok {
    color: @stoa_olive;
}

.analyzer-stat {
    color: @stoa_fg;
}

.analyzer-badge {
    font-size: 0.8em;
    font-weight: 700;
    padding: 1px 8px;
    border-radius: 10px;
    min-width: 20px;
}

.analyzer-badge.analyzer-error {
    background-color: alpha(@stoa_terracotta, 0.2);
    color: @stoa_terracotta;
}

.analyzer-badge.analyzer-warning {
    background-color: alpha(@stoa_gold, 0.2);
    color: @stoa_gold;
}

.analyzer-badge.analyzer-info {
    background-color: alpha(@stoa_azure, 0.2);
    color: @stoa_azure;
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

        # Force dark mode
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

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
