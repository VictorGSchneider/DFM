"""Dotfile wizard - generate base configs for apps that don't have one."""

import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class WizardApp:
    """An application that can have a config generated."""
    name: str
    display_name: str
    command: str  # binary to check
    config_path: str
    description: str
    category: str
    template_key: str  # maps to templates.py


# Apps we can generate configs for
WIZARD_APPS: list[WizardApp] = [
    WizardApp(
        name="i3",
        display_name="i3",
        command="i3",
        config_path="~/.config/i3/config",
        description="Tiling window manager for X11",
        category="Window Managers",
        template_key="i3-minimal",
    ),
    WizardApp(
        name="hyprland",
        display_name="Hyprland",
        command="Hyprland",
        config_path="~/.config/hypr/hyprland.conf",
        description="Dynamic tiling Wayland compositor",
        category="Window Managers",
        template_key="hyprland-minimal",
    ),
    WizardApp(
        name="alacritty",
        display_name="Alacritty",
        command="alacritty",
        config_path="~/.config/alacritty/alacritty.toml",
        description="GPU-accelerated terminal emulator",
        category="Terminal Emulators",
        template_key="alacritty-default",
    ),
    WizardApp(
        name="kitty",
        display_name="Kitty",
        command="kitty",
        config_path="~/.config/kitty/kitty.conf",
        description="GPU-based terminal emulator",
        category="Terminal Emulators",
        template_key="kitty-default",
    ),
    WizardApp(
        name="waybar",
        display_name="Waybar",
        command="waybar",
        config_path="~/.config/waybar/config",
        description="Wayland bar for Sway and Hyprland",
        category="Status Bars",
        template_key="waybar-default",
    ),
    WizardApp(
        name="polybar",
        display_name="Polybar",
        command="polybar",
        config_path="~/.config/polybar/config.ini",
        description="Status bar for i3 and bspwm",
        category="Status Bars",
        template_key="polybar-default",
    ),
    WizardApp(
        name="rofi",
        display_name="Rofi",
        command="rofi",
        config_path="~/.config/rofi/config.rasi",
        description="Application launcher and dmenu replacement",
        category="Launchers",
        template_key="rofi-default",
    ),
    WizardApp(
        name="dunst",
        display_name="Dunst",
        command="dunst",
        config_path="~/.config/dunst/dunstrc",
        description="Notification daemon",
        category="Notifications",
        template_key="dunst-default",
    ),
    WizardApp(
        name="picom",
        display_name="Picom",
        command="picom",
        config_path="~/.config/picom/picom.conf",
        description="X11 compositor for transparency and blur",
        category="System",
        template_key="picom-default",
    ),
    WizardApp(
        name="tmux",
        display_name="Tmux",
        command="tmux",
        config_path="~/.tmux.conf",
        description="Terminal multiplexer",
        category="System",
        template_key="tmux-default",
    ),
    WizardApp(
        name="nvim",
        display_name="Neovim",
        command="nvim",
        config_path="~/.config/nvim/init.lua",
        description="Hyperextensible text editor",
        category="Editors",
        template_key="neovim-minimal",
    ),
    WizardApp(
        name="fish",
        display_name="Fish",
        command="fish",
        config_path="~/.config/fish/config.fish",
        description="Friendly interactive shell",
        category="Shells",
        template_key="fish-default",
    ),
    WizardApp(
        name="zsh",
        display_name="Zsh",
        command="zsh",
        config_path="~/.zshrc",
        description="Z shell with completions",
        category="Shells",
        template_key="zshrc-default",
    ),
]


def get_available_wizards(existing_dotfiles: list) -> list[WizardApp]:
    """Get wizard apps that are installed but don't have configs yet.

    Args:
        existing_dotfiles: List of DotfileEntry objects already detected
    """
    import shutil

    existing_names = {e.name.lower() for e in existing_dotfiles}
    available = []

    for app in WIZARD_APPS:
        # Check if app is installed
        if not shutil.which(app.command):
            continue

        # Check if config already exists
        config_path = os.path.expanduser(app.config_path)
        if os.path.exists(config_path):
            continue

        # Check if already detected (by name)
        if app.name.lower() in existing_names:
            continue

        available.append(app)

    return available


def run_wizard(app: WizardApp) -> str:
    """Generate a config for the given app using its template.

    Returns status message.
    """
    from dfm.core.templates import TEMPLATES, install_template

    # Find the matching template
    for template in TEMPLATES:
        if template.name == app.template_key:
            return install_template(template, backup=True)

    return f"No template found for {app.display_name}"
