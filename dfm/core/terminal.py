"""Open a terminal emulator that runs a command (used to install packages)."""

import os
import shlex
import shutil
import subprocess

# (binary, arguments that introduce the command to run), most capable first.
# Each emulator spells "run this instead of a shell" differently.
_TERMINALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("kitty", ()),
    ("alacritty", ("-e",)),
    ("foot", ()),
    ("wezterm", ("start", "--")),
    ("gnome-terminal", ("--",)),
    ("konsole", ("-e",)),
    ("xfce4-terminal", ("-x",)),
    ("tilix", ("-e",)),
    ("xterm", ("-e",)),
)
_KNOWN = dict(_TERMINALS)
_DEFAULT_EXEC = ("-e",)


def find_terminal() -> tuple[str, tuple[str, ...]] | None:
    """(path, exec arguments) of the terminal to use, or None if there is none.

    Order: $TERMINAL, then the system default (x-terminal-emulator on Debian
    and friends), then the known emulators.
    """
    wanted = os.environ.get("TERMINAL", "").strip()
    for name in (wanted, "x-terminal-emulator"):
        path = shutil.which(name) if name else None
        if path:
            return path, _KNOWN.get(os.path.basename(path), _DEFAULT_EXEC)
    for name, args in _TERMINALS:
        path = shutil.which(name)
        if path:
            return path, args
    return None


def script_for(command: str, done_file: str | None = None) -> str:
    """Shell script that runs `command`, then waits so the output stays readable.

    With `done_file`, the exit code is written there the moment the command
    ends (before the window waits for Enter), or "aborted" if the window is
    closed / interrupted first. The file appears atomically, so a reader never
    sees half of it. This works even for emulators whose launcher process exits
    right away (gnome-terminal), where waiting on the process would not.
    """
    prefix = ""
    record = ""
    if done_file:
        prefix = (
            f"done={shlex.quote(done_file)}; "
            "trap 'echo aborted > \"$done.tmp\" && mv \"$done.tmp\" \"$done\"; exit 1' "
            "HUP TERM INT; "
        )
        record = ('trap - HUP TERM INT; '
                  'echo "$status" > "$done.tmp" && mv "$done.tmp" "$done"; ')
    return (
        f'{prefix}{command}; status=$?; {record}echo; '
        'if [ "$status" -eq 0 ]; then echo "Done."; '
        'else echo "Failed (exit code $status)."; fi; '
        'echo "Press Enter to close."; read -r _'
    )


def open_terminal(command: str, done_file: str | None = None) -> "subprocess.Popen | bool":
    """Run `command` in a new terminal window.

    `done_file` (optional) receives the command's exit code when it finishes;
    see `script_for`. Returns the launched process, or False if no terminal
    could be started.
    """
    found = find_terminal()
    if found is None:
        return False
    path, exec_args = found
    try:
        return subprocess.Popen(
            [path, *exec_args, "sh", "-c", script_for(command, done_file)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
    except OSError:
        return False
