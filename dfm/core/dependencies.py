"""Dependency detection - show what packages dotfiles need."""

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class Dependency:
    """A package dependency for a dotfile."""
    package: str
    description: str
    installed: bool
    optional: bool = False


# Map of dotfile names/patterns to their dependencies
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


def _is_installed(package: str) -> bool:
    """Check if a package is installed via pacman."""
    try:
        result = subprocess.run(
            ["pacman", "-Qi", package],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        # Fallback: check if command exists
        return shutil.which(package) is not None


def get_dependencies(entry) -> list[Dependency]:
    """Get dependencies for a DotfileEntry."""
    name_lower = entry.name.lower()
    display_lower = entry.display_name.lower()

    deps = []
    seen = set()

    for key, dep_list in _DEPENDENCY_MAP.items():
        if key in name_lower or key in display_lower:
            for pkg, desc, optional in dep_list:
                if pkg not in seen:
                    seen.add(pkg)
                    deps.append(Dependency(
                        package=pkg,
                        description=desc,
                        installed=_is_installed(pkg),
                        optional=optional,
                    ))

    return deps


def get_install_command(deps: list[Dependency],
                        only_missing: bool = True) -> str | None:
    """Generate pacman install command for missing dependencies."""
    packages = []
    for dep in deps:
        if only_missing and dep.installed:
            continue
        if not dep.optional or not only_missing:
            packages.append(dep.package)

    if not packages:
        return None

    return f"sudo pacman -S {' '.join(packages)}"
