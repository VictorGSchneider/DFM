"""In-app raw text viewer for dotfiles with syntax highlighting."""

import os
import re

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk, Pango


# Basic syntax patterns for config files
COMMENT_PATTERNS = [
    re.compile(r"(#.*)$", re.MULTILINE),
    re.compile(r"(;.*)$", re.MULTILINE),
    re.compile(r"(//.*$)", re.MULTILINE),
    re.compile(r"(!.*)$", re.MULTILINE),
]

SECTION_PATTERN = re.compile(r"^(\[.+\])$", re.MULTILINE)
KEY_VALUE_PATTERN = re.compile(r"^([\w.\-]+)(\s*[=:]\s*)(.*)", re.MULTILINE)
STRING_PATTERN = re.compile(r'(".*?"|\'.*?\')')
NUMBER_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\b")
BOOL_PATTERN = re.compile(r"\b(true|false|yes|no|on|off)\b", re.IGNORECASE)
COLOR_HEX_PATTERN = re.compile(r"(#[0-9a-fA-F]{3,8})\b")


class TextViewerDialog(Adw.Dialog):
    """Dialog for viewing raw dotfile text content."""

    def __init__(self, title: str, file_path: str) -> None:
        super().__init__()
        self.file_path = file_path
        self.set_title(title)
        self.set_content_width(750)
        self.set_content_height(600)

        self._build_ui()
        self._load_file()

    def _build_ui(self) -> None:
        """Build the viewer UI."""
        toolbar_view = Adw.ToolbarView()

        # Header bar
        header = Adw.HeaderBar()
        header.set_show_title(True)

        # Copy button
        copy_btn = Gtk.Button(icon_name="edit-copy-symbolic",
                              tooltip_text="Copy to clipboard")
        copy_btn.connect("clicked", self._on_copy)
        header.pack_start(copy_btn)

        # Reload button
        reload_btn = Gtk.Button(icon_name="view-refresh-symbolic",
                                tooltip_text="Reload file")
        reload_btn.connect("clicked", self._on_reload)
        header.pack_start(reload_btn)

        # Line wrap toggle
        self.wrap_btn = Gtk.ToggleButton(
            icon_name="format-text-wrapping-symbolic",
            tooltip_text="Toggle line wrapping",
        )
        self.wrap_btn.set_active(False)
        self.wrap_btn.connect("toggled", self._on_wrap_toggled)
        header.pack_end(self.wrap_btn)

        # File info label
        self.info_label = Gtk.Label()
        self.info_label.add_css_class("dim-label")
        header.pack_end(self.info_label)

        toolbar_view.add_top_bar(header)

        # Path bar
        path_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        path_bar.set_margin_start(12)
        path_bar.set_margin_end(12)
        path_bar.set_margin_top(4)
        path_bar.set_margin_bottom(4)
        path_bar.add_css_class("toolbar")

        path_icon = Gtk.Image.new_from_icon_name("folder-symbolic")
        path_bar.append(path_icon)

        path_label = Gtk.Label(label=self.file_path)
        path_label.set_halign(Gtk.Align.START)
        path_label.set_hexpand(True)
        path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        path_label.set_selectable(True)
        path_label.add_css_class("monospace")
        path_bar.append(path_label)

        toolbar_view.add_top_bar(path_bar)

        # Text view
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)

        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_monospace(True)
        self.text_view.set_wrap_mode(Gtk.WrapMode.NONE)
        self.text_view.set_left_margin(8)
        self.text_view.set_right_margin(16)
        self.text_view.set_top_margin(12)
        self.text_view.set_bottom_margin(12)
        self.text_view.add_css_class("view")

        scrolled.set_child(self.text_view)
        toolbar_view.set_content(scrolled)

        # Bottom bar with stats
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bottom_bar.set_margin_start(12)
        bottom_bar.set_margin_end(12)
        bottom_bar.set_margin_top(4)
        bottom_bar.set_margin_bottom(4)

        self.lines_label = Gtk.Label(label="")
        self.lines_label.add_css_class("dim-label")
        bottom_bar.append(self.lines_label)

        self.size_label = Gtk.Label(label="")
        self.size_label.add_css_class("dim-label")
        self.size_label.set_hexpand(True)
        self.size_label.set_halign(Gtk.Align.END)
        bottom_bar.append(self.size_label)

        toolbar_view.add_bottom_bar(bottom_bar)

        self.set_child(toolbar_view)

    def _load_file(self) -> None:
        """Load and display the file content."""
        try:
            with open(self.file_path, "r", errors="replace") as f:
                content = f.read()
        except (PermissionError, FileNotFoundError) as e:
            content = f"Error reading file: {e}"

        buf = self.text_view.get_buffer()

        # Create tags for syntax highlighting
        self._create_tags(buf)

        # Set plain text first
        buf.set_text(content)

        # Apply syntax highlighting
        self._apply_highlighting(buf, content)

        # Update stats
        lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        self.lines_label.set_label(f"{lines} lines")

        file_size = os.path.getsize(self.file_path) if os.path.exists(self.file_path) else 0
        self.size_label.set_label(_format_size(file_size))

        basename = os.path.basename(self.file_path)
        self.info_label.set_label(basename)

    def _create_tags(self, buf: Gtk.TextBuffer) -> None:
        """Create text tags for syntax highlighting."""
        tag_table = buf.get_tag_table()

        tags = {
            "comment": {"foreground": "#7a7267"},      # stoa_fg_dark
            "section": {"foreground": "#c49a5c", "weight": Pango.Weight.BOLD},  # bronze
            "key": {"foreground": "#5a7a8a"},           # azure
            "string": {"foreground": "#8a9a6c"},        # olive
            "number": {"foreground": "#a89272"},         # tan
            "bool": {"foreground": "#c49a5c", "weight": Pango.Weight.BOLD},  # bronze
            "color_hex": {"foreground": "#8a9a6c"},     # olive
            "operator": {"foreground": "#9e9a92"},      # marble
        }

        for name, props in tags.items():
            tag = Gtk.TextTag(name=name)
            for prop, val in props.items():
                if prop == "weight":
                    tag.set_property("weight", val)
                else:
                    tag.set_property(prop, val)
            tag_table.add(tag)

    def _apply_highlighting(self, buf: Gtk.TextBuffer, content: str) -> None:
        """Apply syntax highlighting tags to the buffer."""
        # Comments
        for pattern in COMMENT_PATTERNS:
            for match in pattern.finditer(content):
                start = buf.get_iter_at_offset(match.start(1))
                end = buf.get_iter_at_offset(match.end(1))
                buf.apply_tag_by_name("comment", start, end)

        # Sections [section]
        for match in SECTION_PATTERN.finditer(content):
            start = buf.get_iter_at_offset(match.start(1))
            end = buf.get_iter_at_offset(match.end(1))
            buf.apply_tag_by_name("section", start, end)

        # Key=Value
        for match in KEY_VALUE_PATTERN.finditer(content):
            # Check if inside a comment
            line_start_offset = match.start()
            line_text = content[line_start_offset:match.end()]
            if line_text.lstrip().startswith(("#", ";", "//", "!")):
                continue

            # Key
            start = buf.get_iter_at_offset(match.start(1))
            end = buf.get_iter_at_offset(match.end(1))
            buf.apply_tag_by_name("key", start, end)

            # Operator (= or :)
            start = buf.get_iter_at_offset(match.start(2))
            end = buf.get_iter_at_offset(match.end(2))
            buf.apply_tag_by_name("operator", start, end)

            # Value part - apply sub-highlighting
            val_text = match.group(3)
            val_offset = match.start(3)
            self._highlight_value(buf, val_text, val_offset)

        # Strings in non-key-value lines
        for match in STRING_PATTERN.finditer(content):
            start = buf.get_iter_at_offset(match.start(1))
            end = buf.get_iter_at_offset(match.end(1))
            buf.apply_tag_by_name("string", start, end)

    def _highlight_value(self, buf: Gtk.TextBuffer, text: str,
                         offset: int) -> None:
        """Apply highlighting to a value portion."""
        # Color hex
        for match in COLOR_HEX_PATTERN.finditer(text):
            start = buf.get_iter_at_offset(offset + match.start(1))
            end = buf.get_iter_at_offset(offset + match.end(1))
            buf.apply_tag_by_name("color_hex", start, end)

        # Booleans
        for match in BOOL_PATTERN.finditer(text):
            start = buf.get_iter_at_offset(offset + match.start(1))
            end = buf.get_iter_at_offset(offset + match.end(1))
            buf.apply_tag_by_name("bool", start, end)

        # Strings
        for match in STRING_PATTERN.finditer(text):
            start = buf.get_iter_at_offset(offset + match.start(1))
            end = buf.get_iter_at_offset(offset + match.end(1))
            buf.apply_tag_by_name("string", start, end)

    def _on_copy(self, _btn: Gtk.Button) -> None:
        """Copy file content to clipboard."""
        buf = self.text_view.get_buffer()
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        text = buf.get_text(start, end, False)

        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(text)

        # Brief visual feedback
        _btn.set_icon_name("emblem-ok-symbolic")
        def _restore_icon():
            _btn.set_icon_name("edit-copy-symbolic")
            return False
        GLib.timeout_add(1500, _restore_icon)

    def _on_reload(self, _btn: Gtk.Button) -> None:
        """Reload the file."""
        self._load_file()

    def _on_wrap_toggled(self, btn: Gtk.ToggleButton) -> None:
        """Toggle line wrapping."""
        if btn.get_active():
            self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        else:
            self.text_view.set_wrap_mode(Gtk.WrapMode.NONE)


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
