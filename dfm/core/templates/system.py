"""System-level templates (Picom, Tmux, Neovim)."""

from dfm.core.templates.types import Template


_PICOM_CONTENT = """\
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
"""


_TMUX_CONTENT = """\
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
"""


_NEOVIM_CONTENT = """\
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
"""


SYSTEM: list[Template] = [
    Template(
        name="picom-default",
        app_name="Picom",
        description="Picom compositor with blur, shadows, and animations",
        category="System",
        config_path="~/.config/picom/picom.conf",
        content=_PICOM_CONTENT,
    ),
    Template(
        name="tmux-default",
        app_name="Tmux",
        description="Tmux config with vim-like bindings and status bar",
        category="System",
        config_path="~/.tmux.conf",
        content=_TMUX_CONTENT,
    ),
    Template(
        name="neovim-minimal",
        app_name="Neovim",
        description="Minimal Neovim init.lua with sensible defaults",
        category="Editors",
        config_path="~/.config/nvim/init.lua",
        content=_NEOVIM_CONTENT,
    ),
]
