# DFM - Dotfile Manager

A GTK4/Adwaita GUI application for managing dotfiles on Arch Linux.

**DFM does not move or centralize your dotfiles.** Each config file stays in its original location (`~/.bashrc`, `~/.config/hypr/hyprland.conf`, etc.). DFM detects them, lets you edit in place through a friendly GUI, and creates automatic backups before any change.

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

<!-- ![Analyzer](screenshots/analyzer.png) -->
*Analyzer & Debugger — unified diagnostics for all dotfiles with severity badges and fix hints*

> **Nota:** substitua os placeholders acima pelas screenshots reais. Salve as imagens em `screenshots/` e descomente as linhas `![...]`.

## Features

### In-Place Editing

DFM edits your dotfiles where they live — no symlinking, no moving files into a bare git repo. When you change a value in the GUI, DFM writes directly to the original file. A versioned backup is created automatically before every write, so you can always roll back.

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

### Backup & Versioning

- Automatic backup before every edit
- Versioned history stored in `~/.local/share/dfm/backups/`
- Restore any previous version from the UI

### Profiles & Templates

- Save and switch between configuration profiles (e.g. "desktop", "laptop", "minimal")
- Built-in templates for common setups
- Configuration wizard for quick initial setup

### Analyzer & Debugger

A dedicated diagnostics page that scans all your dotfiles at once and reports issues grouped by severity (errors, warnings, info). Accessible from the sidebar or the Tools menu.

**Per-file checks:**
- Syntax validation for known formats (JSON, TOML, YAML, INI, shell, Xresources)
- Broken symlinks and missing referenced files (`source ~/.zsh_custom` pointing to nothing)
- Duplicate keys that silently shadow earlier values
- Empty values that may be unintentional
- Insecure permissions on sensitive files (world-readable `.netrc`, etc.)
- Deprecated or problematic patterns (double PATH append, eval ssh-agent)
- Missing required and optional package dependencies (checked via pacman)

**Cross-file conflict detection:**
- Environment variables set to different values across shells (e.g. `EDITOR` in `.bashrc` vs `.zshrc`)
- Aliases defined differently in multiple shell configs
- Multiple window managers enabled simultaneously (i3 + Hyprland)
- Multiple notification daemons active (Dunst + Mako)
- Multiple status bars enabled (Waybar + Polybar)

**UI features:**
- Summary cards showing total files scanned, errors, warnings, and healthy count
- Color-coded severity badges (terracotta for errors, gold for warnings, azure for info)
- Fix hints with one-click copy (e.g. `sudo pacman -S hyprland`, `chmod 600 ~/.netrc`)
- Navigate directly from an issue to the dotfile's config page

### File Change Monitoring

- Real-time detection of external edits to tracked dotfiles
- Toast notifications with one-click reload

### GitHub Sync

Sync your dotfiles with GitHub using the community-standard dedicated repo approach (`~/.dotfiles`). **This is the only feature that copies files** — it copies enabled dotfiles into `~/.dotfiles` for pushing to GitHub, but your originals stay in place.

- **Push**: copies enabled dotfiles into the repo, commits, and pushes
- **Pull**: pulls from GitHub and installs to home (existing files are backed up)
- **Create Repo**: creates a new private `dotfiles` repo on GitHub and clones it locally
- **Clone Repo**: clones your existing dotfiles repo from GitHub
- **Share as Gist**: upload an individual dotfile as a GitHub Gist (secret or public) for quick sharing

All GitHub features use the `gh` CLI for authentication, so no tokens are stored by DFM.

### Import / Export

Export your dotfiles as a `.tar.gz` archive with a manifest and import them on another machine. Existing files are backed up before overwriting.

### Stoa-Themed UI

- Classical dark theme inspired by [Stoa Linux](https://github.com/VictorGSchneider/StoaLinux) — marble, bronze, parchment, and stone tones
- Sidebar navigation listing all detected dotfiles with icons and categories
- Right panel with configuration fields grouped by section
- **All Dotfiles** overview page with toggle switches, grouped by category
- **Analyzer & Debugger** page for unified diagnostics
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
├── main.py                # Entry point, application class, CSS
├── core/
│   ├── scanner.py         # Auto-detection of dotfiles on the system
│   ├── parser.py          # Config file parser with smart field type inference
│   ├── backup.py          # Versioned backup system
│   ├── profiles.py        # Profile management (save/switch configs)
│   ├── templates.py       # Built-in config templates
│   ├── wizard.py          # Initial setup wizard
│   ├── validator.py       # Syntax validation for config files
│   ├── conflicts.py       # Conflict detection between configs
│   ├── analyzer.py        # Unified analyzer (syntax, refs, dupes, deps, security)
│   ├── monitor.py         # File change monitoring
│   ├── diff_utils.py      # Diff utilities for comparing versions
│   ├── notes.py           # Per-dotfile user notes
│   ├── dependencies.py    # Dependency checking for detected tools
│   ├── exporter.py        # Import/export as .tar.gz archives
│   └── github_sync.py     # GitHub repo sync and gist sharing via gh CLI
└── ui/
    ├── window.py           # Main window with sidebar + content panel
    ├── window_sidebar.py   # Sidebar navigation
    ├── window_config_page.py # Smart config editing page
    ├── window_all_dotfiles.py # All Dotfiles overview page
    ├── window_analyzer.py  # Analyzer & Debugger diagnostics page
    ├── window_dialogs.py   # Dialogs (backup, profiles, templates, etc.)
    ├── window_sync.py      # GitHub sync UI
    └── viewer.py           # In-app raw text viewer with syntax highlighting
```

## How It Works

1. **Scan** — DFM scans `~/` and `~/.config/` for known dotfiles
2. **Parse** — Each file is analyzed to infer field types (booleans, numbers, colors, paths, etc.)
3. **Display** — A GUI is generated with appropriate widgets for each field
4. **Analyze** — The Analyzer checks syntax, references, duplicates, dependencies, permissions, and cross-file conflicts
5. **Edit** — Changes are written directly to the original file (backup created first)
6. **Sync** (optional) — Copies to `~/.dotfiles` for GitHub push/pull

Your dotfiles never leave home.

## License

GPL-3.0
