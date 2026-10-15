"""Smoke tests for the GTK interface, run against the real app.

Needs GTK 4.12+, libadwaita 1.5+, PyGObject and a display (CI uses Xvfb):

    xvfb-run -a python3 -m unittest discover -s uitests -t .

They are skipped when those aren't available, so the core suite
(`python -m unittest discover -s tests -t .`) never depends on them.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).parent


def _toolkit_problem() -> str | None:
    """Why the UI can't be exercised here, or None if it can."""
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return "no display (run under xvfb-run)"
    probe = ("import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1'); "
             "from gi.repository import Gtk, Adw; "
             "assert (Gtk.get_major_version(), Gtk.get_minor_version()) >= (4, 12); "
             "assert (Adw.get_major_version(), Adw.get_minor_version()) >= (1, 5)")
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True)
    return None if result.returncode == 0 else "GTK 4.12+ / libadwaita 1.5+ / PyGObject not available"


PROBLEM = _toolkit_problem()

# GTK noise that comes from the environment, not from DFM
_IGNORED = ("dbus-launch", "Unable to acquire session bus", "Failed to connect to the accessibility bus",
            "Unable to acquire the address of the accessibility bus")


def _run(script: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HERE / script)], capture_output=True,
                          text=True, timeout=timeout)


def _gtk_problems(stderr: str) -> list[str]:
    """GTK warnings/criticals and tracebacks in `stderr` that DFM caused."""
    return [line for line in stderr.splitlines()
            if any(word in line for word in ("WARNING", "CRITICAL", "Traceback", "Error"))
            and not any(ignored in line for ignored in _IGNORED)]


@unittest.skipIf(PROBLEM, PROBLEM or "")
class UiSmokeTests(unittest.TestCase):
    def test_every_page_and_dialog_builds_without_gtk_warnings(self):
        result = _run("smoke_app.py")
        self.assertIn("SMOKE OK", result.stdout, result.stdout + result.stderr)
        self.assertEqual(_gtk_problems(result.stderr), [], result.stderr)

    def test_editing_every_kind_of_field_writes_the_right_thing(self):
        result = _run("edit_app.py")
        self.assertIn("RESULT ALL OK", result.stdout, result.stdout + result.stderr)
        self.assertEqual(_gtk_problems(result.stderr), [], result.stderr)


if __name__ == "__main__":
    unittest.main()
