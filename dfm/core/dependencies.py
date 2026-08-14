"""Dependency detection - show what packages dotfiles need."""

import os
import shutil
from dataclasses import dataclass

from dfm.core.distro import install_command, is_installed, package_name


@dataclass
class Dependency:
    """A package dependency for a dotfile.

    `package` is the canonical id used by the tables below; `local_name` is
    what the running system's package manager calls it. They are the same on
    Arch, where the canonical ids come from, and differ elsewhere.
    """
    package: str
    description: str
    installed: bool
    optional: bool = False
    local_name: str = ""

    def __post_init__(self) -> None:
        if not self.local_name:
            self.local_name = self.package

    @property
    def display_name(self) -> str:
        """Package name to show the user, annotated when it was translated."""
        if self.local_name != self.package:
            return f"{self.local_name} ({self.package})"
        return self.package


# Map of dotfile names/patterns to their dependencies. Package names here are
# canonical ids (Arch names); dfm.core.distro translates them per system.
_DEPENDENCY_MAP: dict[str, list[tuple[str, str, bool]]] = {
    # (package_name, description, optional)
    "i3": [
        ("i3-wm", "i3 window manager", False),
        ("i3status", "i3 status bar", True),
        ("i3lock", "Screen locker", True),
        ("dmenu", "Application launcher", True),
        ("rofi", "Application launcher (dmenu replacement)", True),
        ("picom", "Compositor for transparency/blur", True),
        ("feh", "Wallpaper setter", True),
        ("dunst", "Notification daemon", True),
    ],
    "sway": [
        ("sway", "Sway Wayland compositor", False),
        ("swaylock", "Screen locker for Sway", True),
        ("swayidle", "Idle management", True),
        ("waybar", "Status bar for Wayland", True),
        ("wofi", "Application launcher for Wayland", True),
        ("mako", "Notification daemon for Wayland", True),
        ("grim", "Screenshot utility", True),
        ("slurp", "Region selector", True),
    ],
    "hyprland": [
        ("hyprland", "Hyprland Wayland compositor", False),
        ("hyprlock", "Screen locker", True),
        ("hypridle", "Idle management", True),
        ("waybar", "Status bar", True),
        ("wofi", "Application launcher", True),
        ("dunst", "Notification daemon", True),
        ("grim", "Screenshot utility", True),
        ("slurp", "Region selector", True),
        ("hyprpaper", "Wallpaper utility", True),
    ],
    "alacritty": [
        ("alacritty", "Alacritty terminal emulator", False),
    ],
    "kitty": [
        ("kitty", "Kitty terminal emulator", False),
    ],
    "foot": [
        ("foot", "Foot terminal emulator", False),
    ],
    "wezterm": [
        ("wezterm", "WezTerm terminal emulator", False),
    ],
    "waybar": [
        ("waybar", "Waybar status bar", False),
        ("otf-font-awesome", "Font Awesome icons", True),
        ("ttf-nerd-fonts-symbols", "Nerd Font symbols", True),
    ],
    "polybar": [
        ("polybar", "Polybar status bar", False),
        ("ttf-font-awesome", "Font Awesome icons", True),
    ],
    "rofi": [
        ("rofi", "Rofi application launcher", False),
    ],
    "wofi": [
        ("wofi", "Wofi application launcher", False),
    ],
    "dunst": [
        ("dunst", "Dunst notification daemon", False),
    ],
    "mako": [
        ("mako", "Mako notification daemon", False),
    ],
    "neovim": [
        ("neovim", "Neovim text editor", False),
        ("nodejs", "Node.js (for CoC/Mason LSPs)", True),
        ("npm", "npm package manager", True),
        ("python-pynvim", "Python Neovim bindings", True),
        ("ripgrep", "Fast search (Telescope)", True),
        ("fd", "Fast find (Telescope)", True),
    ],
    "nvim": [
        ("neovim", "Neovim text editor", False),
        ("nodejs", "Node.js (for CoC/Mason LSPs)", True),
        ("ripgrep", "Fast search (Telescope)", True),
        ("fd", "Fast find (Telescope)", True),
    ],
    "vim": [
        ("vim", "Vim text editor", False),
    ],
    "awesome": [
        ("awesome", "Awesome window manager", False),
        ("lua", "Lua interpreter", True),
    ],
    "xplr": [
        ("xplr", "xplr file manager", False),
    ],
    "fish": [
        ("fish", "Fish shell", False),
    ],
    "zsh": [
        ("zsh", "Zsh shell", False),
        ("zsh-completions", "Additional completions", True),
        ("zsh-syntax-highlighting", "Syntax highlighting", True),
        ("zsh-autosuggestions", "Auto-suggestions", True),
    ],
    "tmux": [
        ("tmux", "Terminal multiplexer", False),
    ],
    "mpv": [
        ("mpv", "MPV media player", False),
    ],
    "cava": [
        ("cava", "Console audio visualizer", False),
        ("pulseaudio", "PulseAudio (or pipewire-pulse)", True),
    ],
    "picom": [
        ("picom", "Compositor", False),
    ],
    "git": [
        ("git", "Git version control", False),
    ],
    "gtk": [
        ("gtk3", "GTK3 toolkit", True),
        ("gtk4", "GTK4 toolkit", True),
    ],
}


def _make(package: str, description: str, optional: bool,
          installed: bool | None = None) -> Dependency:
    return Dependency(
        package=package,
        description=description,
        installed=is_installed(package) if installed is None else installed,
        optional=optional,
        local_name=package_name(package),
    )


def get_dependencies(entry) -> list[Dependency]:
    """Get dependencies for a DotfileEntry."""
    name_lower = entry.name.lower()
    display_lower = entry.display_name.lower()

    deps = []
    seen = set()

    for key, dep_list in _DEPENDENCY_MAP.items():
        if key == name_lower or key == display_lower:
            for pkg, desc, optional in dep_list:
                if pkg not in seen:
                    seen.add(pkg)
                    deps.append(_make(pkg, desc, optional))

    config_path = entry.get_config_path() or entry.path
    if os.path.splitext(str(config_path))[1].lower() == ".lua" and "lua" not in seen:
        deps.append(_make(
            "lua",
            "Lua interpreter (luac validates Lua configs)",
            True,
            installed=is_installed("lua") or shutil.which("luac") is not None,
        ))

    return deps


def get_install_command(deps: list[Dependency],
                        only_missing: bool = True) -> str | None:
    """Install command for the given dependencies, in the local package
    manager's syntax. None if nothing is missing, or if we don't recognise
    this system's package manager."""
    packages = []
    for dep in deps:
        if only_missing and dep.installed:
            continue
        if not dep.optional or not only_missing:
            packages.append(dep.package)

    return install_command(packages)
