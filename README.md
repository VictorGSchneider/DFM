# DFM - Dotfile Manager

A GTK4/Adwaita GUI application for managing dotfiles on Arch Linux.

## Screenshots

<!-- Para adicionar screenshots:
     1. Rode o app: python -m dfm.main
     2. Tire screenshots e salve na pasta screenshots/
     3. Descomente as linhas abaixo correspondentes
-->

<!-- ![Main window - All Dotfiles](screenshots/all-dotfiles.png) -->
*All Dotfiles — overview page with toggle switches to enable/disable each dotfile*

<!-- ![Config page](screenshots/config-page.png) -->
*Config page — smart fields generated from the config file (toggles, sliders, color pickers, text fields)*

<!-- ![Raw text viewer](screenshots/raw-viewer.png) -->
*Raw text viewer — syntax highlighted view of the dotfile with copy and line wrap*

<!-- ![GitHub Sync](screenshots/github-sync.png) -->
*GitHub Sync — push/pull dotfiles to a GitHub repo, share as Gist*

> **Nota:** substitua os placeholders acima pelas screenshots reais. Salve as imagens em `screenshots/` e descomente as linhas `![...]`.

## Features

### Smart Config Parsing

Automatically scans your system for known dotfiles and config directories (`~/.config/*`), analyzes each file, and generates the appropriate UI controls:

- Toggle switches for boolean values (`true`/`false`, `yes`/`no`, `on`/`off`)
- Sliders for numeric values (opacity, gaps, borders, etc.)
- Color pickers for hex color values
- Text fields for strings
- Path selectors with file browser for file paths
- Spin buttons for numeric values
- Font fields
- Keybind display for keyboard shortcuts
- Section headers parsed from comments

### Raw Text Viewer

Built-in viewer for inspecting dotfiles without leaving the app:

- Syntax highlighting (comments, keys, values, colors, booleans)
- Copy to clipboard
- Line wrap toggle
- Reload button
- File stats (line count, file size)

### GitHub Sync

Sync your dotfiles with GitHub using the community-standard dedicated repo approach (`~/.dotfiles`):

- **Push**: copies enabled dotfiles into the repo, commits, and pushes
- **Pull**: pulls from GitHub and installs to home (existing files are backed up as `.dfm_backup`)
- **Create Repo**: creates a new private `dotfiles` repo on GitHub and clones it locally
- **Clone Repo**: clones your existing dotfiles repo from GitHub
- **Share as Gist**: upload an individual dotfile as a GitHub Gist (secret or public) for quick sharing

All GitHub features use the `gh` CLI for authentication, so no tokens are stored by DFM.

### Import / Export

Export your dotfiles as a `.tar.gz` archive with a manifest and import them on another machine. Existing files are backed up before overwriting.

### GNOME Settings-Inspired UI

- Sidebar navigation listing all detected dotfiles with icons
- Right panel with configuration fields grouped by section
- **All Dotfiles** overview page with toggle switches to enable/disable each dotfile, grouped by category
- GitHub Sync status and controls integrated into the overview page

## Supported Dotfiles

| Category | Examples |
|---|---|
| Shells | `.bashrc`, `.zshrc`, `.profile`, Fish |
| Window Managers | i3, Sway, Hyprland, BSPWM, Awesome, Openbox, Herbstluftwm |
| Terminals | Alacritty, Kitty, Foot, WezTerm |
| Status Bars | Waybar, Polybar |
| Launchers | Rofi, Wofi |
| Notifications | Dunst, Mako |
| Editors | Vim, Neovim, Nano |
| Media | MPV, CAVA, PipeWire, PulseAudio |
| Appearance | GTK 3/4, Qt5/6, Fontconfig |
| Development | Git |
| System | Starship, Ranger, LF, Btop, Htop, Neofetch, Fastfetch, and more |

80+ known config files and directories are detected automatically.

## Dependencies

- Python 3.10+
- GTK 4
- libadwaita
- PyGObject
- GitHub CLI (`gh`) — optional, required for GitHub sync features

### Install on Arch Linux

```bash
# Required
sudo pacman -S python python-gobject gtk4 libadwaita

# Optional (for GitHub sync)
sudo pacman -S github-cli
gh auth login
```

## Usage

```bash
# Run directly
python -m dfm.main

# Or install and run
pip install -e .
dfm
```

## Project Structure

```
dfm/
├── main.py          # Entry point, application class, CSS
├── window.py        # Main window with sidebar + content panel
├── scanner.py       # Auto-detection of dotfiles on the system
├── parser.py        # Config file parser with smart field type inference
├── viewer.py        # In-app raw text viewer with syntax highlighting
├── exporter.py      # Import/export as .tar.gz archives
├── github_sync.py   # GitHub repo sync and gist sharing via gh CLI
└── style.css        # Additional styles
```

## License

GPL-3.0
