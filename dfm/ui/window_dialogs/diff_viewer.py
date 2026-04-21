"""Show a unified diff with syntax highlighting."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk, Pango

from dfm.core.diff_utils import diff_stats
from dfm.ui.window_dialogs._common import (
    make_dialog, present_dialog, set_dialog_content,
)


DIFF_COLORS = {
    "addition": "#8a9a6c",   # stoa olive
    "deletion": "#b36b5a",   # stoa terracotta
    "context": "#7a7267",    # stoa fg_dark
    "header": "#5a7a8a",     # stoa azure
    "hunk": "#c49a5c",       # stoa bronze
}


class DiffViewerDialog:
    """Show a unified diff with syntax highlighting."""

    def __init__(self, parent_window, title: str, diff_text: str) -> None:
        self.parent_window = parent_window
        self.diff_text = diff_text
        self.dialog = make_dialog(title, width=750, height=600)
        self._build_ui()

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_show_title(True)
        copy_btn = Gtk.Button(
            icon_name="edit-copy-symbolic", tooltip_text="Copy diff to clipboard",
        )
        copy_btn.connect("clicked", self._on_copy)
        header.pack_start(copy_btn)
        toolbar_view.add_top_bar(header)

        toolbar_view.add_top_bar(self._build_stats_bar())

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)

        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_monospace(True)
        self.text_view.set_wrap_mode(Gtk.WrapMode.NONE)
        self.text_view.set_left_margin(16)
        self.text_view.set_right_margin(16)
        self.text_view.set_top_margin(12)
        self.text_view.set_bottom_margin(12)

        buf = self.text_view.get_buffer()
        self._register_tags(buf)
        buf.set_text(self.diff_text)
        self._apply_diff_highlighting(buf)

        scrolled.set_child(self.text_view)
        toolbar_view.set_content(scrolled)
        set_dialog_content(self.dialog, toolbar_view)

    def _build_stats_bar(self) -> Gtk.Box:
        adds, dels = diff_stats(self.diff_text)
        stats_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        stats_bar.set_margin_start(16)
        stats_bar.set_margin_end(16)
        stats_bar.set_margin_top(6)
        stats_bar.set_margin_bottom(6)

        if adds > 0:
            adds_label = Gtk.Label(label=f"+{adds}")
            adds_label.add_css_class("success")
            stats_bar.append(adds_label)
        if dels > 0:
            dels_label = Gtk.Label(label=f"-{dels}")
            dels_label.add_css_class("error")
            stats_bar.append(dels_label)
        if adds == 0 and dels == 0:
            no_changes = Gtk.Label(label="No changes")
            no_changes.add_css_class("dim-label")
            stats_bar.append(no_changes)

        total_label = Gtk.Label(label=f"{len(self.diff_text.splitlines())} lines")
        total_label.add_css_class("dim-label")
        total_label.set_hexpand(True)
        total_label.set_halign(Gtk.Align.END)
        stats_bar.append(total_label)
        return stats_bar

    def _register_tags(self, buf: Gtk.TextBuffer) -> None:
        tag_table = buf.get_tag_table()
        for name, color in DIFF_COLORS.items():
            tag = Gtk.TextTag(name=name)
            tag.set_property("foreground", color)
            if name == "header":
                tag.set_property("weight", Pango.Weight.BOLD)
            tag_table.add(tag)

    def _apply_diff_highlighting(self, buf: Gtk.TextBuffer) -> None:
        offset = 0
        for line in self.diff_text.splitlines(keepends=True):
            start = buf.get_iter_at_offset(offset)
            end = buf.get_iter_at_offset(offset + len(line))

            if line.startswith("+++") or line.startswith("---"):
                buf.apply_tag_by_name("header", start, end)
            elif line.startswith("@@"):
                buf.apply_tag_by_name("hunk", start, end)
            elif line.startswith("+"):
                buf.apply_tag_by_name("addition", start, end)
            elif line.startswith("-"):
                buf.apply_tag_by_name("deletion", start, end)
            else:
                buf.apply_tag_by_name("context", start, end)
            offset += len(line)

    def _on_copy(self, btn: Gtk.Button) -> None:
        Gdk.Display.get_default().get_clipboard().set(self.diff_text)
        btn.set_icon_name("emblem-ok-symbolic")

        def _restore_icon():
            btn.set_icon_name("edit-copy-symbolic")
            return False

        GLib.timeout_add(1500, _restore_icon)

    def present(self) -> None:
        present_dialog(self.dialog, self.parent_window)
