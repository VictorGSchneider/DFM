"""Dotfile scanner - auto-detects dotfiles on the system."""

import os
from pathlib import Path
from dataclasses import dataclass, field


# Well-known dotfiles and their descriptions
KNOWN_DOTFILES = {
    ".bashrc": "Bash Shell",
    ".zshrc": "Zsh Shell",
    ".bash_profile": "Bash Profile",
    ".zprofile": "Zsh Profile",
    ".profile": "Shell Profile",
    ".vimrc": "Vim",
    ".gvimrc": "GVim",
    ".tmux.conf": "Tmux",
    ".gitconfig": "Git",
    ".gitignore_global": "Git Ignore Global",
    ".Xresources": "X Resources",
    ".Xdefaults": "X Defaults",
    ".xinitrc": "X Init",
    ".xprofile": "X Profile",
    ".fehbg": "Feh Background",
    ".inputrc": "Readline",
    ".screenrc": "GNU Screen",
    ".nanorc": "Nano",
    ".wgetrc": "Wget",
    ".curlrc": "Curl",
    ".aliases": "Aliases",
    ".dir_colors": "Dir Colors",
    ".editorconfig": "EditorConfig",
    ".taskrc": "Taskwarrior",
}

KNOWN_CONFIG_DIRS = {
    "i3": "i3 Window Manager",
    "sway": "Sway",
    "hypr": "Hyprland",
    "hyprland": "Hyprland",
    "waybar": "Waybar",
    "polybar": "Polybar",
    "rofi": "Rofi",
    "wofi": "Wofi",
    "dunst": "Dunst",
    "picom": "Picom",
    "alacritty": "Alacritty",
    "kitty": "Kitty",
    "foot": "Foot",
    "wezterm": "WezTerm",
    "neovim": "Neovim",
    "nvim": "Neovim",
    "fish": "Fish Shell",
    "starship": "Starship Prompt",
    "ranger": "Ranger",
    "lf": "LF File Manager",
    "yay": "Yay (AUR Helper)",
    "paru": "Paru (AUR Helper)",
    "fontconfig": "Font Config",
    "gtk-3.0": "GTK 3",
    "gtk-4.0": "GTK 4",
    "qt5ct": "Qt5 Config",
    "qt6ct": "Qt6 Config",
    "mpv": "MPV Player",
    "zathura": "Zathura",
    "sxhkd": "SXHKD",
    "bspwm": "BSPWM",
    "awesome": "Awesome WM",
    "openbox": "Openbox",
    "fluxbox": "Fluxbox",
    "herbstluftwm": "Herbstluftwm",
    "mako": "Mako (Notifications)",
    "swaylock": "Swaylock",
    "swayidle": "Swayidle",
    "kanshi": "Kanshi (Display Config)",
    "wlogout": "Wlogout",
    "nwg-launchers": "NWG Launchers",
    "Code - OSS": "VS Code (OSS)",
    "Code": "VS Code",
    "electron-flags.conf": "Electron Flags",
    "bat": "Bat",
    "htop": "Htop",
    "btop": "Btop",
    "neofetch": "Neofetch",
    "fastfetch": "Fastfetch",
    "cava": "CAVA (Audio Visualizer)",
    "pulse": "PulseAudio",
    "pipewire": "PipeWire",
    "wireplumber": "WirePlumber",
    "systemd": "Systemd (User)",
    "environment.d": "Environment Variables",
    "mimeapps.list": "MIME Apps",
    "user-dirs.dirs": "User Directories",
}

# Config file patterns within config directories
CONFIG_FILE_PATTERNS = [
    "config",
    "config.ini",
    "config.toml",
    "config.yaml",
    "config.yml",
    "config.json",
    "config.conf",
    "settings.ini",
    "settings.conf",
    "rc.conf",
    "*.conf",
    "*.ini",
    "*.toml",
    "*.yaml",
    "*.yml",
]


@dataclass
class DotfileEntry:
    """Represents a discovered dotfile."""
    name: str
    display_name: str
    path: str
    is_directory: bool = False
    config_file: str = ""
    enabled: bool = True
    icon_name: str = "document-properties-symbolic"

    def get_config_path(self) -> str:
        """Return the main config file path."""
        if self.config_file:
            return self.config_file
        return self.path


def scan_dotfiles(home_dir: str | None = None) -> list[DotfileEntry]:
    """Scan the system for dotfiles and config directories."""
    if home_dir is None:
        home_dir = str(Path.home())

    entries = []

    # Scan home directory for known dotfiles
    for filename, display_name in KNOWN_DOTFILES.items():
        filepath = os.path.join(home_dir, filename)
        if os.path.exists(filepath):
            entries.append(DotfileEntry(
                name=filename,
                display_name=display_name,
                path=filepath,
                is_directory=False,
                icon_name=_get_icon_for_dotfile(filename),
            ))

    # Scan .config directory
    config_dir = os.path.join(home_dir, ".config")
    if os.path.isdir(config_dir):
        for dirname, display_name in KNOWN_CONFIG_DIRS.items():
            dirpath = os.path.join(config_dir, dirname)
            if os.path.exists(dirpath):
                config_file = _find_config_file(dirpath)
                if os.path.isdir(dirpath) and config_file:
                    entries.append(DotfileEntry(
                        name=dirname,
                        display_name=display_name,
                        path=dirpath,
                        is_directory=True,
                        config_file=config_file,
                        icon_name=_get_icon_for_config(dirname),
                    ))
                elif os.path.isfile(dirpath):
                    entries.append(DotfileEntry(
                        name=dirname,
                        display_name=display_name,
                        path=dirpath,
                        is_directory=False,
                        icon_name=_get_icon_for_config(dirname),
                    ))

    # Sort by display name
    entries.sort(key=lambda e: e.display_name.lower())
    return entries


def _find_config_file(dirpath: str) -> str:
    """Find the main config file in a directory."""
    # Check exact names first
    exact_names = ["config", "config.conf", "config.ini", "config.toml",
                   "config.yaml", "config.yml", "config.json",
                   "settings.ini", "settings.conf", "rc.conf"]
    for name in exact_names:
        filepath = os.path.join(dirpath, name)
        if os.path.isfile(filepath):
            return filepath

    # Check for any config-like file
    try:
        for f in os.listdir(dirpath):
            fpath = os.path.join(dirpath, f)
            if os.path.isfile(fpath):
                ext = os.path.splitext(f)[1].lower()
                if ext in (".conf", ".ini", ".toml", ".yaml", ".yml", ".json", ".cfg"):
                    return fpath
    except PermissionError:
        pass

    # Fallback: any readable file
    try:
        for f in os.listdir(dirpath):
            fpath = os.path.join(dirpath, f)
            if os.path.isfile(fpath) and not f.startswith("."):
                try:
                    with open(fpath, "r") as fh:
                        fh.read(1)
                    return fpath
                except (UnicodeDecodeError, PermissionError):
                    continue
    except PermissionError:
        pass

    return ""


def _get_icon_for_dotfile(filename: str) -> str:
    """Get an appropriate icon name for a dotfile."""
    icons = {
        ".bashrc": "utilities-terminal-symbolic",
        ".zshrc": "utilities-terminal-symbolic",
        ".bash_profile": "utilities-terminal-symbolic",
        ".zprofile": "utilities-terminal-symbolic",
        ".profile": "utilities-terminal-symbolic",
        ".vimrc": "text-editor-symbolic",
        ".gvimrc": "text-editor-symbolic",
        ".tmux.conf": "utilities-terminal-symbolic",
        ".gitconfig": "git-symbolic",
        ".Xresources": "preferences-desktop-display-symbolic",
        ".xinitrc": "preferences-desktop-display-symbolic",
    }
    return icons.get(filename, "document-properties-symbolic")


def _get_icon_for_config(dirname: str) -> str:
    """Get an appropriate icon name for a config directory."""
    icons = {
        "i3": "preferences-desktop-display-symbolic",
        "sway": "preferences-desktop-display-symbolic",
        "hypr": "preferences-desktop-display-symbolic",
        "hyprland": "preferences-desktop-display-symbolic",
        "waybar": "preferences-desktop-display-symbolic",
        "polybar": "preferences-desktop-display-symbolic",
        "alacritty": "utilities-terminal-symbolic",
        "kitty": "utilities-terminal-symbolic",
        "foot": "utilities-terminal-symbolic",
        "wezterm": "utilities-terminal-symbolic",
        "nvim": "text-editor-symbolic",
        "neovim": "text-editor-symbolic",
        "fish": "utilities-terminal-symbolic",
        "rofi": "system-search-symbolic",
        "dunst": "preferences-system-notifications-symbolic",
        "mako": "preferences-system-notifications-symbolic",
        "mpv": "multimedia-video-player-symbolic",
        "pipewire": "audio-volume-high-symbolic",
        "pulse": "audio-volume-high-symbolic",
        "fontconfig": "preferences-desktop-font-symbolic",
        "gtk-3.0": "preferences-desktop-theme-symbolic",
        "gtk-4.0": "preferences-desktop-theme-symbolic",
    }
    return icons.get(dirname, "application-x-executable-symbolic")
