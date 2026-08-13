"""Terminal emulator templates (Alacritty, Kitty)."""

from dfm.core.templates.types import Template


_ALACRITTY_CONTENT = """\
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
"""


_KITTY_CONTENT = """\
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
"""


_WEZTERM_CONTENT = """\
-- WezTerm config - template by DFM

local wezterm = require("wezterm")
local config = wezterm.config_builder()

config.color_scheme = "Catppuccin Mocha"
config.font = wezterm.font("JetBrainsMono Nerd Font")
config.font_size = 12.0
config.line_height = 1.1

config.window_background_opacity = 0.95
config.hide_tab_bar_if_only_one_tab = true
config.use_fancy_tab_bar = false
config.scrollback_lines = 10000
config.enable_scroll_bar = false
config.audible_bell = "Disabled"

config.window_padding = {
    left = 8,
    right = 8,
    top = 8,
    bottom = 8,
}

return config
"""


TERMINALS: list[Template] = [
    Template(
        name="wezterm-default",
        app_name="WezTerm",
        description="WezTerm config in Lua with a dark theme and sensible padding",
        category="Terminal Emulators",
        config_path="~/.config/wezterm/wezterm.lua",
        content=_WEZTERM_CONTENT,
    ),
    Template(
        name="alacritty-default",
        app_name="Alacritty",
        description="Modern Alacritty config with Catppuccin-inspired colors",
        category="Terminal Emulators",
        config_path="~/.config/alacritty/alacritty.toml",
        content=_ALACRITTY_CONTENT,
    ),
    Template(
        name="kitty-default",
        app_name="Kitty",
        description="Kitty terminal config with good defaults and dark theme",
        category="Terminal Emulators",
        config_path="~/.config/kitty/kitty.conf",
        content=_KITTY_CONTENT,
    ),
]
