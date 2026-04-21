"""Window manager templates (i3, Hyprland)."""

from dfm.core.templates.types import Template


_I3_CONTENT = """\
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
"""


_HYPRLAND_CONTENT = """\
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
"""


WINDOW_MANAGERS: list[Template] = [
    Template(
        name="i3-minimal",
        app_name="i3",
        description="Minimal i3 config with sensible defaults, gaps, and common keybinds",
        category="Window Managers",
        config_path="~/.config/i3/config",
        content=_I3_CONTENT,
    ),
    Template(
        name="hyprland-minimal",
        app_name="Hyprland",
        description="Clean Hyprland config with animations, gaps, and common binds",
        category="Window Managers",
        config_path="~/.config/hypr/hyprland.conf",
        content=_HYPRLAND_CONTENT,
    ),
]
