"""Pre-made config templates for popular applications."""

import os
import shutil
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Template:
    """A configuration template."""
    name: str
    app_name: str
    description: str
    category: str
    config_path: str  # Where it should be installed
    content: str


# ── Template definitions ────────────────────────────────────────────

TEMPLATES: list[Template] = [
    Template(
        name="i3-minimal",
        app_name="i3",
        description="Minimal i3 config with sensible defaults, gaps, and common keybinds",
        category="Window Managers",
        config_path="~/.config/i3/config",
        content="""\
# i3 config - minimal template by DFM
set $mod Mod4

# Font
font pango:monospace 10

# Gaps
gaps inner 8
gaps outer 4

# Window borders
default_border pixel 2
default_floating_border pixel 2

# Colors
client.focused          #4c7899 #285577 #ffffff #2e9ef4 #285577
client.focused_inactive #333333 #5f676a #ffffff #484e50 #5f676a
client.unfocused        #333333 #222222 #888888 #292d2e #222222

# Key bindings
bindsym $mod+Return exec alacritty
bindsym $mod+d exec rofi -show drun
bindsym $mod+q kill
bindsym $mod+Shift+r restart
bindsym $mod+Shift+e exec i3-nagbar -t warning -m 'Exit i3?' -B 'Yes' 'i3-msg exit'

# Navigation
bindsym $mod+h focus left
bindsym $mod+j focus down
bindsym $mod+k focus up
bindsym $mod+l focus right

bindsym $mod+Shift+h move left
bindsym $mod+Shift+j move down
bindsym $mod+Shift+k move up
bindsym $mod+Shift+l move right

# Workspaces
set $ws1 "1"
set $ws2 "2"
set $ws3 "3"
set $ws4 "4"
set $ws5 "5"

bindsym $mod+1 workspace $ws1
bindsym $mod+2 workspace $ws2
bindsym $mod+3 workspace $ws3
bindsym $mod+4 workspace $ws4
bindsym $mod+5 workspace $ws5

bindsym $mod+Shift+1 move container to workspace $ws1
bindsym $mod+Shift+2 move container to workspace $ws2
bindsym $mod+Shift+3 move container to workspace $ws3
bindsym $mod+Shift+4 move container to workspace $ws4
bindsym $mod+Shift+5 move container to workspace $ws5

# Layout
bindsym $mod+s layout stacking
bindsym $mod+w layout tabbed
bindsym $mod+e layout toggle split
bindsym $mod+f fullscreen toggle
bindsym $mod+Shift+space floating toggle

# Resize
bindsym $mod+r mode "resize"
mode "resize" {
    bindsym h resize shrink width 5 px
    bindsym j resize grow height 5 px
    bindsym k resize shrink height 5 px
    bindsym l resize grow width 5 px
    bindsym Escape mode "default"
}

# Autostart
exec --no-startup-id picom
exec --no-startup-id dunst
exec_always --no-startup-id $HOME/.config/polybar/launch.sh
""",
    ),
    Template(
        name="hyprland-minimal",
        app_name="Hyprland",
        description="Clean Hyprland config with animations, gaps, and common binds",
        category="Window Managers",
        config_path="~/.config/hypr/hyprland.conf",
        content="""\
# Hyprland config - minimal template by DFM

monitor=,preferred,auto,1

general {
    gaps_in = 5
    gaps_out = 10
    border_size = 2
    col.active_border = rgba(33ccffee) rgba(00ff99ee) 45deg
    col.inactive_border = rgba(595959aa)
    layout = dwindle
}

decoration {
    rounding = 10
    blur {
        enabled = true
        size = 3
        passes = 1
    }
    shadow {
        enabled = true
        range = 4
        render_power = 3
    }
}

animations {
    enabled = yes
    bezier = myBezier, 0.05, 0.9, 0.1, 1.05
    animation = windows, 1, 7, myBezier
    animation = windowsOut, 1, 7, default, popin 80%
    animation = border, 1, 10, default
    animation = fade, 1, 7, default
    animation = workspaces, 1, 6, default
}

input {
    kb_layout = us
    follow_mouse = 1
    sensitivity = 0
}

dwindle {
    pseudotile = yes
    preserve_split = yes
}

$mainMod = SUPER
bind = $mainMod, Return, exec, alacritty
bind = $mainMod, Q, killactive,
bind = $mainMod, M, exit,
bind = $mainMod, E, exec, thunar
bind = $mainMod, V, togglefloating,
bind = $mainMod, D, exec, rofi -show drun
bind = $mainMod, F, fullscreen,

bind = $mainMod, H, movefocus, l
bind = $mainMod, L, movefocus, r
bind = $mainMod, K, movefocus, u
bind = $mainMod, J, movefocus, d

bind = $mainMod, 1, workspace, 1
bind = $mainMod, 2, workspace, 2
bind = $mainMod, 3, workspace, 3
bind = $mainMod, 4, workspace, 4
bind = $mainMod, 5, workspace, 5

bind = $mainMod SHIFT, 1, movetoworkspace, 1
bind = $mainMod SHIFT, 2, movetoworkspace, 2
bind = $mainMod SHIFT, 3, movetoworkspace, 3
bind = $mainMod SHIFT, 4, movetoworkspace, 4
bind = $mainMod SHIFT, 5, movetoworkspace, 5

bindm = $mainMod, mouse:272, movewindow
bindm = $mainMod, mouse:273, resizewindow

exec-once = waybar
exec-once = dunst
""",
    ),
    Template(
        name="alacritty-default",
        app_name="Alacritty",
        description="Modern Alacritty config with Catppuccin-inspired colors",
        category="Terminal Emulators",
        config_path="~/.config/alacritty/alacritty.toml",
        content="""\
# Alacritty config - template by DFM

[window]
padding.x = 8
padding.y = 8
opacity = 0.95
decorations = "None"

[font]
size = 12.0
normal.family = "JetBrainsMono Nerd Font"
bold.family = "JetBrainsMono Nerd Font"
italic.family = "JetBrainsMono Nerd Font"

[cursor]
style.shape = "Block"
style.blinking = "On"
vi_mode_style.shape = "Beam"

[colors.primary]
background = "#1e1e2e"
foreground = "#cdd6f4"

[colors.normal]
black   = "#45475a"
red     = "#f38ba8"
green   = "#a6e3a1"
yellow  = "#f9e2af"
blue    = "#89b4fa"
magenta = "#f5c2e7"
cyan    = "#94e2d5"
white   = "#bac2de"

[colors.bright]
black   = "#585b70"
red     = "#f38ba8"
green   = "#a6e3a1"
yellow  = "#f9e2af"
blue    = "#89b4fa"
magenta = "#f5c2e7"
cyan    = "#94e2d5"
white   = "#a6adc8"
""",
    ),
    Template(
        name="kitty-default",
        app_name="Kitty",
        description="Kitty terminal config with good defaults and dark theme",
        category="Terminal Emulators",
        config_path="~/.config/kitty/kitty.conf",
        content="""\
# Kitty config - template by DFM

font_family      JetBrainsMono Nerd Font
bold_font        auto
italic_font      auto
font_size        12.0

cursor_shape     block
cursor_blink_interval 0.5

scrollback_lines 10000
mouse_hide_wait  3.0

window_padding_width 8
background_opacity 0.95
confirm_os_window_close 0

# Colors (Catppuccin Mocha)
foreground #cdd6f4
background #1e1e2e

color0  #45475a
color1  #f38ba8
color2  #a6e3a1
color3  #f9e2af
color4  #89b4fa
color5  #f5c2e7
color6  #94e2d5
color7  #bac2de

color8  #585b70
color9  #f38ba8
color10 #a6e3a1
color11 #f9e2af
color12 #89b4fa
color13 #f5c2e7
color14 #94e2d5
color15 #a6adc8
""",
    ),
    Template(
        name="waybar-default",
        app_name="Waybar",
        description="Waybar config with workspaces, clock, system tray, and more",
        category="Status Bars",
        config_path="~/.config/waybar/config",
        content="""\
{
    "layer": "top",
    "position": "top",
    "height": 32,
    "spacing": 4,
    "modules-left": ["hyprland/workspaces", "hyprland/window"],
    "modules-center": ["clock"],
    "modules-right": ["pulseaudio", "network", "cpu", "memory", "battery", "tray"],

    "clock": {
        "format": "{:%H:%M}",
        "format-alt": "{:%Y-%m-%d %H:%M}",
        "tooltip-format": "<big>{:%Y %B}</big>\\n<tt><small>{calendar}</small></tt>"
    },
    "cpu": {
        "format": " {usage}%",
        "tooltip": true
    },
    "memory": {
        "format": " {}%"
    },
    "battery": {
        "states": {
            "warning": 30,
            "critical": 15
        },
        "format": "{icon} {capacity}%",
        "format-icons": ["", "", "", "", ""]
    },
    "network": {
        "format-wifi": " {signalStrength}%",
        "format-ethernet": " Connected",
        "format-disconnected": "⚠ Disconnected"
    },
    "pulseaudio": {
        "format": "{icon} {volume}%",
        "format-muted": " Muted",
        "format-icons": {
            "default": ["", "", ""]
        }
    },
    "tray": {
        "spacing": 10
    }
}
""",
    ),
    Template(
        name="polybar-default",
        app_name="Polybar",
        description="Polybar config with workspaces, system info, and clean look",
        category="Status Bars",
        config_path="~/.config/polybar/config.ini",
        content="""\
; Polybar config - template by DFM

[colors]
background = #1e1e2e
foreground = #cdd6f4
primary = #89b4fa
secondary = #a6e3a1
alert = #f38ba8

[bar/main]
width = 100%
height = 28
radius = 0
fixed-center = true
background = ${colors.background}
foreground = ${colors.foreground}
padding-left = 1
padding-right = 2
module-margin-left = 1
module-margin-right = 1
font-0 = "monospace:size=10;2"
font-1 = "Font Awesome 6 Free:style=Solid:size=10;2"
modules-left = i3
modules-center = date
modules-right = pulseaudio memory cpu

[module/i3]
type = internal/i3
pin-workspaces = true
strip-wsnumbers = true

[module/cpu]
type = internal/cpu
interval = 2
format-prefix = "CPU "
format-prefix-foreground = ${colors.primary}
label = %percentage%%

[module/memory]
type = internal/memory
interval = 2
format-prefix = "MEM "
format-prefix-foreground = ${colors.primary}
label = %percentage_used%%

[module/date]
type = internal/date
interval = 5
date = %Y-%m-%d
time = %H:%M
label = %date% %time%

[module/pulseaudio]
type = internal/pulseaudio
format-volume = VOL <label-volume>
label-volume = %percentage%%
label-muted = MUTED
""",
    ),
    Template(
        name="rofi-default",
        app_name="Rofi",
        description="Clean rofi config with dark theme",
        category="Launchers",
        config_path="~/.config/rofi/config.rasi",
        content="""\
/* Rofi config - template by DFM */

configuration {
    modi: "drun,run,window";
    show-icons: true;
    terminal: "alacritty";
    font: "monospace 12";
}

* {
    bg: #1e1e2e;
    fg: #cdd6f4;
    accent: #89b4fa;
    urgent: #f38ba8;
}

window {
    width: 600px;
    background-color: @bg;
    border: 2px;
    border-color: @accent;
    border-radius: 10px;
    padding: 20px;
}

inputbar {
    children: [prompt, entry];
    background-color: @bg;
    border-radius: 5px;
    padding: 8px;
}

prompt {
    background-color: @accent;
    text-color: @bg;
    padding: 4px 8px;
    border-radius: 4px;
}

entry {
    padding: 4px;
    text-color: @fg;
}

listview {
    lines: 8;
    columns: 1;
    fixed-height: true;
    spacing: 4px;
}

element {
    padding: 8px;
    border-radius: 5px;
}

element selected {
    background-color: @accent;
    text-color: @bg;
}
""",
    ),
    Template(
        name="dunst-default",
        app_name="Dunst",
        description="Dunst notification config with dark theme and sane defaults",
        category="Notifications",
        config_path="~/.config/dunst/dunstrc",
        content="""\
# Dunst config - template by DFM

[global]
    width = 300
    height = 300
    offset = 10x40
    origin = top-right
    transparency = 10
    frame_width = 2
    frame_color = "#89b4fa"
    font = monospace 10
    markup = full
    format = "<b>%s</b>\\n%b"
    alignment = left
    show_age_threshold = 60
    icon_position = left
    max_icon_size = 64
    corner_radius = 10
    mouse_left_click = close_current
    mouse_right_click = close_all

[urgency_low]
    background = "#1e1e2e"
    foreground = "#cdd6f4"
    timeout = 5

[urgency_normal]
    background = "#1e1e2e"
    foreground = "#cdd6f4"
    timeout = 10

[urgency_critical]
    background = "#1e1e2e"
    foreground = "#f38ba8"
    frame_color = "#f38ba8"
    timeout = 0
""",
    ),
    Template(
        name="picom-default",
        app_name="Picom",
        description="Picom compositor with blur, shadows, and animations",
        category="System",
        config_path="~/.config/picom/picom.conf",
        content="""\
# Picom config - template by DFM

backend = "glx";
vsync = true;

# Opacity
active-opacity = 1.0;
inactive-opacity = 0.9;
frame-opacity = 1.0;

# Blur
blur-method = "dual_kawase";
blur-strength = 5;

# Shadow
shadow = true;
shadow-radius = 12;
shadow-offset-x = -5;
shadow-offset-y = -5;
shadow-opacity = 0.5;

# Fading
fading = true;
fade-in-step = 0.03;
fade-out-step = 0.03;

# Corners
corner-radius = 10;

# Exclude
shadow-exclude = [
    "class_g = 'Polybar'",
];

opacity-rule = [
    "95:class_g = 'Alacritty'",
    "95:class_g = 'kitty'",
];
""",
    ),
    Template(
        name="tmux-default",
        app_name="Tmux",
        description="Tmux config with vim-like bindings and status bar",
        category="System",
        config_path="~/.tmux.conf",
        content="""\
# Tmux config - template by DFM

# Prefix
unbind C-b
set -g prefix C-a
bind C-a send-prefix

# General
set -g mouse on
set -g base-index 1
setw -g pane-base-index 1
set -g renumber-windows on
set -g default-terminal "tmux-256color"
set -ag terminal-overrides ",xterm-256color:RGB"

# Vim-like pane navigation
bind h select-pane -L
bind j select-pane -D
bind k select-pane -U
bind l select-pane -R

# Split panes
bind | split-window -h -c "#{pane_current_path}"
bind - split-window -v -c "#{pane_current_path}"
unbind '"'
unbind %

# Resize panes
bind -r H resize-pane -L 5
bind -r J resize-pane -D 5
bind -r K resize-pane -U 5
bind -r L resize-pane -R 5

# Status bar
set -g status-position bottom
set -g status-style bg=#1e1e2e,fg=#cdd6f4
set -g status-left '#[fg=#89b4fa,bold] #S '
set -g status-right '#[fg=#a6e3a1] %H:%M #[fg=#89b4fa] %Y-%m-%d '
set -g status-left-length 30

# Reload
bind r source-file ~/.tmux.conf \\; display "Reloaded!"
""",
    ),
    Template(
        name="neovim-minimal",
        app_name="Neovim",
        description="Minimal Neovim init.lua with sensible defaults",
        category="Editors",
        config_path="~/.config/nvim/init.lua",
        content="""\
-- Neovim config - minimal template by DFM

-- Options
vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.tabstop = 4
vim.opt.shiftwidth = 4
vim.opt.expandtab = true
vim.opt.smartindent = true
vim.opt.wrap = false
vim.opt.cursorline = true
vim.opt.termguicolors = true
vim.opt.signcolumn = "yes"
vim.opt.clipboard = "unnamedplus"
vim.opt.scrolloff = 8
vim.opt.updatetime = 250
vim.opt.ignorecase = true
vim.opt.smartcase = true
vim.opt.splitbelow = true
vim.opt.splitright = true
vim.opt.undofile = true
vim.opt.mouse = "a"

-- Leader
vim.g.mapleader = " "

-- Keymaps
vim.keymap.set("n", "<leader>w", ":w<CR>", { desc = "Save" })
vim.keymap.set("n", "<leader>q", ":q<CR>", { desc = "Quit" })
vim.keymap.set("n", "<C-h>", "<C-w>h", { desc = "Move left" })
vim.keymap.set("n", "<C-j>", "<C-w>j", { desc = "Move down" })
vim.keymap.set("n", "<C-k>", "<C-w>k", { desc = "Move up" })
vim.keymap.set("n", "<C-l>", "<C-w>l", { desc = "Move right" })
vim.keymap.set("n", "<leader>e", ":Explore<CR>", { desc = "File explorer" })
vim.keymap.set("v", "J", ":m '>+1<CR>gv=gv", { desc = "Move line down" })
vim.keymap.set("v", "K", ":m '<-2<CR>gv=gv", { desc = "Move line up" })
""",
    ),
    Template(
        name="fish-default",
        app_name="Fish",
        description="Fish shell config with useful aliases and prompt",
        category="Shells",
        config_path="~/.config/fish/config.fish",
        content="""\
# Fish config - template by DFM

# Disable greeting
set -g fish_greeting ""

# Environment
set -gx EDITOR nvim
set -gx VISUAL nvim

# Path
fish_add_path ~/.local/bin

# Aliases
alias ls='ls --color=auto'
alias ll='ls -la'
alias la='ls -A'
alias grep='grep --color=auto'
alias vim='nvim'
alias ..='cd ..'
alias ...='cd ../..'

# Git aliases
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git log --oneline --graph'
alias gd='git diff'

# System
alias update='sudo pacman -Syu'
alias cleanup='sudo pacman -Rns (pacman -Qdtq)'

# Prompt colors
set -g fish_color_command green
set -g fish_color_param normal
set -g fish_color_error red --bold
set -g fish_color_comment brblack
""",
    ),
    Template(
        name="zshrc-default",
        app_name="Zsh",
        description="Zsh config with history, completions, and useful aliases",
        category="Shells",
        config_path="~/.zshrc",
        content="""\
# Zsh config - template by DFM

# History
HISTSIZE=10000
SAVEHIST=10000
HISTFILE=~/.zsh_history
setopt HIST_IGNORE_DUPS
setopt HIST_IGNORE_SPACE
setopt SHARE_HISTORY

# Completion
autoload -Uz compinit && compinit
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'

# Key bindings (vim mode)
bindkey -v
bindkey '^R' history-incremental-search-backward

# Environment
export EDITOR=nvim
export VISUAL=nvim
export PATH="$HOME/.local/bin:$PATH"

# Aliases
alias ls='ls --color=auto'
alias ll='ls -la'
alias la='ls -A'
alias grep='grep --color=auto'
alias vim='nvim'
alias ..='cd ..'
alias ...='cd ../..'

# Git aliases
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git log --oneline --graph'

# Prompt
autoload -Uz vcs_info
precmd() { vcs_info }
zstyle ':vcs_info:git:*' formats '%b '
setopt PROMPT_SUBST
PROMPT='%F{blue}%~%f %F{green}${vcs_info_msg_0_}%f%# '
""",
    ),
]


def get_templates() -> list[Template]:
    """Get all available templates."""
    return TEMPLATES


def get_templates_by_category() -> dict[str, list[Template]]:
    """Get templates grouped by category."""
    groups: dict[str, list[Template]] = {}
    for t in TEMPLATES:
        groups.setdefault(t.category, []).append(t)
    return groups


def install_template(template: Template, backup: bool = True) -> str:
    """Install a template to the filesystem.

    Returns status message.
    """
    target = os.path.expanduser(template.config_path)
    target_dir = os.path.dirname(target)

    os.makedirs(target_dir, exist_ok=True)

    if os.path.isfile(target) and backup:
        from dfm.core.backup import create_backup
        create_backup(target, reason=f"template:{template.name}")

    with open(target, "w") as f:
        f.write(template.content)

    return f"Installed {template.app_name} template to {target}"
