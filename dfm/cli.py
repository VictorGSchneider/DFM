"""Command-line entry point. Kept free of GTK so `dfm --version` works anywhere."""

import sys

from dfm import __version__


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if any(a in ("--version", "-V") for a in args):
        print(f"dfm {__version__}")
        return 0

    from dfm.main import main as run_gui  # imports GTK: only when we need the window
    run_gui()
    return 0
