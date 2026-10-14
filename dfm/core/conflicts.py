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


# Known conflict patterns (matched against one stripped, non-comment line)
_ENV_VAR_PATTERN = re.compile(r"^export\s+([A-Za-z_]\w*)=(.*)$")
_FISH_ENV_PATTERN = re.compile(r"^set\s+(?:-[A-Za-z]+\s+)*([A-Za-z_]\w*)\s+(\S.*)$")
_ALIAS_PATTERN = re.compile(r"^alias\s+([^\s=]+)(?:=|\s+)(.+)$")
_PATH_PATTERNS = {
    "EDITOR": "Default editor",
    "VISUAL": "Visual editor",
    "TERMINAL": "Default terminal",
    "BROWSER": "Default browser",
    "SHELL": "Default shell",
    "PAGER": "Default pager",
}


def _unquote(value: str) -> str:
    """Strip one matching pair of surrounding quotes, like a shell would."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


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
            with open(config_path, errors="replace") as f:
                content = f.read()
        except OSError:
            continue

        is_fish = "fish" in name_lower or "fish" in display_lower
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = _ENV_VAR_PATTERN.match(line)
            if match is None and is_fish:
                match = _FISH_ENV_PATTERN.match(line)
            if match:
                env_vars.setdefault(match.group(1), []).append(
                    (entry.display_name, _unquote(match.group(2))))
                continue

            match = _ALIAS_PATTERN.match(line)
            if match:
                aliases.setdefault(match.group(1), []).append(
                    (entry.display_name, _unquote(match.group(2))))

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
