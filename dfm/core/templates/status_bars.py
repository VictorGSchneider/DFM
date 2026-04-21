"""Status bar, launcher, and notification templates."""

from dfm.core.templates.types import Template


_WAYBAR_CONTENT = """\
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
"""


_POLYBAR_CONTENT = """\
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
"""


_ROFI_CONTENT = """\
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
"""


_DUNST_CONTENT = """\
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
"""


STATUS_BARS: list[Template] = [
    Template(
        name="waybar-default",
        app_name="Waybar",
        description="Waybar config with workspaces, clock, system tray, and more",
        category="Status Bars",
        config_path="~/.config/waybar/config",
        content=_WAYBAR_CONTENT,
    ),
    Template(
        name="polybar-default",
        app_name="Polybar",
        description="Polybar config with workspaces, system info, and clean look",
        category="Status Bars",
        config_path="~/.config/polybar/config.ini",
        content=_POLYBAR_CONTENT,
    ),
    Template(
        name="rofi-default",
        app_name="Rofi",
        description="Clean rofi config with dark theme",
        category="Launchers",
        config_path="~/.config/rofi/config.rasi",
        content=_ROFI_CONTENT,
    ),
    Template(
        name="dunst-default",
        app_name="Dunst",
        description="Dunst notification config with dark theme and sane defaults",
        category="Notifications",
        config_path="~/.config/dunst/dunstrc",
        content=_DUNST_CONTENT,
    ),
]
