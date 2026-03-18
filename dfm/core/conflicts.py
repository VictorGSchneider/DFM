"""Conflict detection between dotfiles."""

import os
import re
from dataclasses import dataclass
from dfm.core.scanner import DotfileEntry


@dataclass
class Conflict:
    """A detected conflict between two dotfiles."""
    key: str
    description: str
    entries: list[str]  # display names of conflicting dotfiles
    severity: str = "warning"  # "info", "warning", "error"


# Known conflict patterns
_ENV_VAR_PATTERN = re.compile(
    r'(?:export\s+|set\s+-gx\s+|set\s+)(\w+)\s*=?\s*(.+)', re.MULTILINE
)
_ALIAS_PATTERN = re.compile(
    r'(?:alias\s+)(\w+)\s*=\s*(.+)', re.MULTILINE
)
_PATH_PATTERNS = {
    "EDITOR": "Default editor",
    "VISUAL": "Visual editor",
    "TERMINAL": "Default terminal",
    "BROWSER": "Default browser",
    "SHELL": "Default shell",
    "PAGER": "Default pager",
}


def detect_conflicts(entries: list[DotfileEntry]) -> list[Conflict]:
    """Detect conflicts across all dotfile entries."""
    conflicts = []

    # Collect environment variables and aliases from shell configs
    env_vars: dict[str, list[tuple[str, str]]] = {}
    aliases: dict[str, list[tuple[str, str]]] = {}

    shell_names = {"bash", "zsh", "fish", "shell"}

    for entry in entries:
        if not entry.enabled:
            continue

        name_lower = entry.name.lower()
        display_lower = entry.display_name.lower()

        is_shell = any(s in name_lower or s in display_lower
                       for s in shell_names)

        if not is_shell:
            continue

        config_path = entry.get_config_path()
        if not config_path or not os.path.isfile(config_path):
            continue

        try:
            with open(config_path) as f:
                content = f.read()
        except OSError:
            continue

        # Find env vars
        for match in _ENV_VAR_PATTERN.finditer(content):
            var_name = match.group(1)
            var_value = match.group(2).strip().strip('"\'')
            env_vars.setdefault(var_name, []).append(
                (entry.display_name, var_value)
            )

        # Find aliases
        for match in _ALIAS_PATTERN.finditer(content):
            alias_name = match.group(1)
            alias_value = match.group(2).strip().strip('"\'')
            aliases.setdefault(alias_name, []).append(
                (entry.display_name, alias_value)
            )

    # Check for conflicting env vars
    for var_name, definitions in env_vars.items():
        if len(definitions) < 2:
            continue

        values = set(v for _, v in definitions)
        if len(values) > 1:
            desc = _PATH_PATTERNS.get(var_name, f"Environment variable {var_name}")
            entry_names = [d[0] for d in definitions]
            details = ", ".join(f"{name}={val}" for name, val in definitions)
            conflicts.append(Conflict(
                key=var_name,
                description=f"{desc} set to different values: {details}",
                entries=entry_names,
                severity="warning",
            ))

    # Check for conflicting aliases
    for alias_name, definitions in aliases.items():
        if len(definitions) < 2:
            continue

        values = set(v for _, v in definitions)
        if len(values) > 1:
            entry_names = [d[0] for d in definitions]
            details = ", ".join(f"{name}={val}" for name, val in definitions)
            conflicts.append(Conflict(
                key=f"alias:{alias_name}",
                description=f"Alias '{alias_name}' defined differently: {details}",
                entries=entry_names,
                severity="info",
            ))

    # Check for WM conflicts (multiple WMs configured to autostart)
    wm_names = {"i3", "sway", "hypr", "hyprland", "bspwm", "awesome",
                "openbox", "herbstluftwm", "fluxbox"}
    active_wms = []
    for entry in entries:
        if not entry.enabled:
            continue
        name_lower = entry.name.lower()
        if any(wm in name_lower for wm in wm_names):
            active_wms.append(entry.display_name)

    if len(active_wms) > 1:
        conflicts.append(Conflict(
            key="window_manager",
            description=f"Multiple window managers enabled: {', '.join(active_wms)}. "
                        "Only one should be active at a time.",
            entries=active_wms,
            severity="warning",
        ))

    # Check for notification daemon conflicts
    notif_names = {"dunst", "mako", "swaync"}
    active_notifs = []
    for entry in entries:
        if not entry.enabled:
            continue
        name_lower = entry.name.lower()
        if any(n in name_lower for n in notif_names):
            active_notifs.append(entry.display_name)

    if len(active_notifs) > 1:
        conflicts.append(Conflict(
            key="notification_daemon",
            description=f"Multiple notification daemons enabled: {', '.join(active_notifs)}",
            entries=active_notifs,
            severity="warning",
        ))

    # Check for bar conflicts
    bar_names = {"waybar", "polybar"}
    active_bars = []
    for entry in entries:
        if not entry.enabled:
            continue
        name_lower = entry.name.lower()
        if any(b in name_lower for b in bar_names):
            active_bars.append(entry.display_name)

    if len(active_bars) > 1:
        conflicts.append(Conflict(
            key="status_bar",
            description=f"Multiple status bars enabled: {', '.join(active_bars)}",
            entries=active_bars,
            severity="info",
        ))

    return conflicts
