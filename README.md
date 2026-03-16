# DFM - Dotfile Manager

A GTK4/Adwaita GUI application for managing dotfiles on Arch Linux.

## Features

- **Auto-detection**: Automatically scans your system for known dotfiles and config directories (~/.config/*)
- **Smart Config Parsing**: Analyzes config files and generates appropriate UI controls:
  - Toggle switches for boolean values
  - Sliders for numeric values (opacity, gaps, borders, etc.)
  - Color pickers for color values
  - Text fields for strings
  - Path selectors for file paths
  - Keybind display for keyboard shortcuts
- **Import/Export**: Export your dotfiles as a `.tar.gz` archive and import them on another machine
- **GNOME Settings-inspired UI**: Sidebar navigation with dotfile list, right panel with configuration fields
- **All Dotfiles Overview**: Special page to enable/disable dotfiles with toggle switches

## Supported Dotfiles

- Shells: `.bashrc`, `.zshrc`, `.profile`, Fish
- Window Managers: i3, Sway, Hyprland, BSPWM, Awesome, Openbox
- Terminals: Alacritty, Kitty, Foot, WezTerm
- Bars: Waybar, Polybar
- Editors: Vim, Neovim, Nano
- And many more (80+ known configs)

## Dependencies

- Python 3.10+
- GTK 4
- libadwaita
- PyGObject

### Install on Arch Linux

```bash
sudo pacman -S python python-gobject gtk4 libadwaita
```

## Usage

```bash
# Run directly
python -m dfm.main

# Or install and run
pip install -e .
dfm
```

## License

GPL-3.0
