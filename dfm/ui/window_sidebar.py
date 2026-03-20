import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Pango
from enum import Enum, auto
from dfm.core.scanner import DotfileEntry
from dfm.core.notes import get_favorites, get_note


class SortMode(Enum):
    NAME_ASC = auto()
    NAME_DESC = auto()
    CATEGORY = auto()
    PATH = auto()


SORT_LABELS = {
    SortMode.NAME_ASC: "Name (A-Z)",
    SortMode.NAME_DESC: "Name (Z-A)",
    SortMode.CATEGORY: "Category",
    SortMode.PATH: "Path",
}

CATEGORY_ICONS = {
    "Shells": "utilities-terminal-symbolic",
    "Window Managers": "preferences-desktop-display-symbolic",
    "Terminal Emulators": "utilities-terminal-symbolic",
    "Status Bars": "preferences-desktop-display-symbolic",
    "Launchers": "system-search-symbolic",
    "Notifications": "preferences-system-notifications-symbolic",
    "Editors": "text-editor-symbolic",
    "Media": "multimedia-video-player-symbolic",
    "Appearance": "preferences-desktop-theme-symbolic",
    "Development": "utilities-terminal-symbolic",
    "System": "preferences-system-symbolic",
}


def _categorize(entry: DotfileEntry) -> str:
    name = entry.name.lower()
    display = entry.display_name.lower()
    terminals = {"alacritty", "kitty", "foot", "wezterm"}
    shells = {"bash", "zsh", "fish", "shell"}
    wms = {
        "i3", "sway", "hypr", "hyprland", "bspwm", "awesome",
        "openbox", "herbstluftwm", "fluxbox",
    }
    bars = {"waybar", "polybar"}
    launchers = {"rofi", "wofi"}
    notifications = {"dunst", "mako"}
    editors = {"vim", "nvim", "neovim", "nano"}
    media = {"mpv", "cava", "pipewire", "pulse", "wireplumber"}
    if any(t in name or t in display for t in terminals):
        return "Terminal Emulators"
    if any(s in name or s in display for s in shells):
        return "Shells"
    if any(w in name or w in display for w in wms):
        return "Window Managers"
    if any(b in name or b in display for b in bars):
        return "Status Bars"
    if any(l in name or l in display for l in launchers):
        return "Launchers"
    if any(n in name or n in display for n in notifications):
        return "Notifications"
    if any(e in name or e in display for e in editors):
        return "Editors"
    if any(m in name or m in display for m in media):
        return "Media"
    if "gtk" in name or "qt" in name or "font" in name or "theme" in display:
        return "Appearance"
    if "git" in name:
        return "Development"
    return "System"


def _group_by_category(
    dotfiles: list[DotfileEntry],
) -> dict[str, list[DotfileEntry]]:
    groups: dict[str, list[DotfileEntry]] = {}
    for entry in dotfiles:
        cat = _categorize(entry)
        groups.setdefault(cat, []).append(entry)
    return groups


def _sort_entries(
    dotfiles: list[DotfileEntry], mode: SortMode
) -> list[DotfileEntry]:
    if mode == SortMode.NAME_ASC:
        return sorted(dotfiles, key=lambda e: e.display_name.lower())
    elif mode == SortMode.NAME_DESC:
        return sorted(dotfiles, key=lambda e: e.display_name.lower(), reverse=True)
    elif mode == SortMode.CATEGORY:
        return sorted(dotfiles, key=lambda e: (_categorize(e), e.display_name.lower()))
    elif mode == SortMode.PATH:
        return sorted(dotfiles, key=lambda e: str(e.path).lower())
    return dotfiles


class SidebarManager:
    def __init__(self, on_entry_selected):
        self.on_entry_selected = on_entry_selected
        self.dotfiles: list[DotfileEntry] = []
        self.sort_mode: SortMode = SortMode.NAME_ASC
        self.filter_text: str = ""
        self.sidebar_expanded: dict[str, bool] = {}
        self._tree_box: Gtk.Box | None = None
        self._search_entry: Gtk.SearchEntry | None = None

    def build(self) -> Gtk.Box:
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar.set_size_request(260, -1)
        sidebar.add_css_class("sidebar")

        # Search entry
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("Filter dotfiles\u2026")
        self._search_entry.set_hexpand(True)
        self._search_entry.add_css_class("sidebar-search")
        self._search_entry.connect("search-changed", self._on_search_changed)

        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        search_box.set_margin_top(8)
        search_box.set_margin_bottom(4)
        search_box.set_margin_start(8)
        search_box.set_margin_end(8)
        search_box.append(self._search_entry)
        sidebar.append(search_box)

        # Sort dropdown
        sort_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        sort_box.set_margin_start(8)
        sort_box.set_margin_end(8)
        sort_box.set_margin_bottom(8)

        sort_label = Gtk.Label(label="Sort:")
        sort_label.add_css_class("dim-label")
        sort_box.append(sort_label)

        sort_strings = Gtk.StringList.new(
            [SORT_LABELS[m] for m in SortMode]
        )
        self._sort_dropdown = Gtk.DropDown(model=sort_strings)
        self._sort_dropdown.set_hexpand(True)
        self._sort_dropdown.connect("notify::selected", self._on_sort_changed)
        sort_box.append(self._sort_dropdown)
        sidebar.append(sort_box)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sidebar.append(separator)

        # Scrollable tree area
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        self._tree_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scrolled.set_child(self._tree_box)
        sidebar.append(scrolled)

        return sidebar

    def populate(self, dotfiles: list[DotfileEntry]) -> None:
        self.dotfiles = list(dotfiles)
        self._rebuild_tree()

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self.filter_text = entry.get_text().strip().lower()
        self._rebuild_tree()

    def _on_sort_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        idx = dropdown.get_selected()
        modes = list(SortMode)
        if 0 <= idx < len(modes):
            self.sort_mode = modes[idx]
        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        if self._tree_box is None:
            return

        # Clear existing children
        while True:
            child = self._tree_box.get_first_child()
            if child is None:
                break
            self._tree_box.remove(child)

        # Filter
        if self.filter_text:
            filtered = [
                e for e in self.dotfiles
                if self.filter_text in e.display_name.lower()
            ]
        else:
            filtered = list(self.dotfiles)

        # Sort
        sorted_entries = _sort_entries(filtered, self.sort_mode)

        # "All Dotfiles" row
        all_row = self._make_all_dotfiles_row()
        self._tree_box.append(all_row)

        # Favorites section (read once, not per-row)
        self._cached_favorites = set(get_favorites())
        favorites = self._cached_favorites
        fav_entries = [e for e in sorted_entries if e.name in favorites]
        if fav_entries:
            fav_header = self._make_category_header(
                "Favorites", "starred-symbolic", len(fav_entries)
            )
            self._tree_box.append(fav_header)

            expanded = self.sidebar_expanded.get("Favorites", True)
            fav_items_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            if not expanded:
                fav_items_box.set_visible(False)
            for entry in fav_entries:
                row = self._make_dotfile_row(entry)
                fav_items_box.append(row)
            fav_header._items_box = fav_items_box
            self._tree_box.append(fav_items_box)

        # Group by category
        groups = _group_by_category(sorted_entries)
        sorted_categories = sorted(groups.keys())

        for cat in sorted_categories:
            entries = groups[cat]
            # Sort entries within category based on current sort mode
            if self.sort_mode == SortMode.NAME_ASC:
                entries = sorted(entries, key=lambda e: e.display_name.lower())
            elif self.sort_mode == SortMode.NAME_DESC:
                entries = sorted(
                    entries, key=lambda e: e.display_name.lower(), reverse=True
                )
            elif self.sort_mode == SortMode.PATH:
                entries = sorted(entries, key=lambda e: str(e.path).lower())

            icon_name = CATEGORY_ICONS.get(cat, "folder-symbolic")
            header = self._make_category_header(cat, icon_name, len(entries))
            self._tree_box.append(header)

            expanded = self.sidebar_expanded.get(cat, True)
            items_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            if not expanded:
                items_box.set_visible(False)
            for entry in entries:
                row = self._make_dotfile_row(entry)
                items_box.append(row)
            header._items_box = items_box
            self._tree_box.append(items_box)

    def _make_all_dotfiles_row(self) -> Gtk.Button:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)

        icon = Gtk.Image.new_from_icon_name("starred-symbolic")
        icon.set_pixel_size(16)
        box.append(icon)

        label = Gtk.Label(label="All Dotfiles")
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(label)

        button = Gtk.Button()
        button.set_child(box)
        button.add_css_class("flat")
        button.set_hexpand(True)
        button.connect("clicked", self._on_all_dotfiles_clicked)
        return button

    def _on_all_dotfiles_clicked(self, _button: Gtk.Button) -> None:
        self.on_entry_selected(None)

    def _make_category_header(
        self, category: str, icon_name: str, count: int
    ) -> Gtk.Button:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(6)
        box.set_margin_bottom(2)

        expanded = self.sidebar_expanded.get(category, True)
        arrow = Gtk.Image.new_from_icon_name(
            "pan-down-symbolic" if expanded else "pan-end-symbolic"
        )
        arrow.set_pixel_size(12)
        box.append(arrow)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(16)
        box.append(icon)

        name_label = Gtk.Label(label=category)
        name_label.set_halign(Gtk.Align.START)
        name_label.set_hexpand(True)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.add_css_class("heading")
        box.append(name_label)

        count_label = Gtk.Label(label=str(count))
        count_label.add_css_class("dim-label")
        box.append(count_label)

        button = Gtk.Button()
        button.set_child(box)
        button.add_css_class("flat")
        button.set_hexpand(True)
        button._category = category
        button._arrow = arrow
        button._items_box = None  # set after creation
        button.connect("clicked", self._on_category_clicked)
        return button

    def _on_category_clicked(self, button: Gtk.Button) -> None:
        category = button._category
        currently_expanded = self.sidebar_expanded.get(category, True)
        new_state = not currently_expanded
        self.sidebar_expanded[category] = new_state

        button._arrow.set_from_icon_name(
            "pan-down-symbolic" if new_state else "pan-end-symbolic"
        )
        if button._items_box is not None:
            button._items_box.set_visible(new_state)

    def _make_dotfile_row(self, entry: DotfileEntry) -> Gtk.Button:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(32)
        box.set_margin_end(8)
        box.set_margin_top(2)
        box.set_margin_bottom(2)

        # Use cached favorites from _rebuild_tree instead of reading file per row
        favorites = getattr(self, '_cached_favorites', set())
        if entry.name in favorites:
            star = Gtk.Image.new_from_icon_name("starred-symbolic")
            star.set_pixel_size(12)
            box.append(star)

        label = Gtk.Label(label=entry.display_name)
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(label)

        button = Gtk.Button()
        button.set_child(box)
        button.add_css_class("flat")
        button.set_hexpand(True)
        button._entry = entry
        button.connect("clicked", self._on_dotfile_clicked)
        return button

    def _on_dotfile_clicked(self, button: Gtk.Button) -> None:
        self.on_entry_selected(button._entry)
