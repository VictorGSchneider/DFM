"""Opening a terminal that runs the install command for missing packages."""

import os
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from dfm.core import distro, terminal
from dfm.core.analyzer_types import FileAnalysis, FullAnalysis
from dfm.core.dependencies import Dependency
from dfm.core.scanner import DotfileEntry


def fake_bin(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.bin = Path(tempfile.mkdtemp())
        # Look for terminals only among our fakes (a dev machine may have real
        # ones), but keep the real PATH so the fakes can exec `sh`.
        real_which = shutil.which
        for patcher in (
            mock.patch.object(terminal.shutil, "which",
                              lambda name, **kw: real_which(name, path=str(self.bin))),
            mock.patch.dict(os.environ, {}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        os.environ.pop("TERMINAL", None)

    def test_no_terminal_installed(self):
        self.assertIsNone(terminal.find_terminal())
        self.assertFalse(terminal.open_terminal("echo hi"))

    def test_picks_a_known_terminal_with_its_own_exec_flag(self):
        fake_bin(self.bin, "gnome-terminal", "")
        self.assertEqual(terminal.find_terminal(),
                         (str(self.bin / "gnome-terminal"), ("--",)))

    def test_terminal_env_var_wins_and_x_terminal_emulator_beats_the_table(self):
        fake_bin(self.bin, "xterm", "")
        fake_bin(self.bin, "kitty", "")
        self.assertEqual(terminal.find_terminal()[0], str(self.bin / "kitty"))
        fake_bin(self.bin, "x-terminal-emulator", "")
        self.assertEqual(terminal.find_terminal()[0], str(self.bin / "x-terminal-emulator"))
        with mock.patch.dict(os.environ, {"TERMINAL": "xterm"}):
            self.assertEqual(terminal.find_terminal()[0], str(self.bin / "xterm"))

    def test_command_runs_in_the_terminal_and_the_window_waits_for_enter(self):
        marker = self.bin / "ran.txt"
        fake_bin(self.bin, "xterm", 'shift\nexec "$@"\n')  # xterm -e CMD...
        proc = terminal.open_terminal(f"echo ok > {marker}")
        self.assertTrue(proc)
        proc.wait(timeout=10)
        self.assertEqual(marker.read_text().strip(), "ok")

    def test_script_runs_the_command_then_waits_for_enter(self):
        script = terminal.script_for("sudo apt install a b")
        self.assertTrue(script.startswith("sudo apt install a b;"))
        self.assertIn("Press Enter", script)

    def _run(self, command, wait=True):
        fake_bin(self.bin, "xterm", 'shift\nexec "$@"\n')
        done = self.bin / "done"
        proc = terminal.open_terminal(command, done_file=str(done))
        self.assertTrue(proc)
        if wait:
            proc.wait(timeout=10)
        return proc, done

    def test_status_file_says_the_command_finished_successfully(self):
        _, done = self._run("true")
        self.assertEqual(done.read_text().strip(), "0")

    def test_status_file_carries_the_exit_code_of_a_failed_command(self):
        _, done = self._run("sh -c 'exit 3'")
        self.assertEqual(done.read_text().strip(), "3")

    def test_status_is_written_before_the_user_closes_the_window(self):
        # The window waits for Enter after the command; DFM must not have to.
        fake_bin(self.bin, "xterm", 'shift\nexec "$@"\n')
        done = self.bin / "done"
        fifo = self.bin / "fifo"
        os.mkfifo(fifo)  # `read` blocks on it like a terminal waiting for Enter
        script = terminal.script_for("true", str(done)).replace("read -r _", f"read -r _ < {fifo}")
        proc = subprocess.Popen(["sh", "-c", script], start_new_session=True)
        for _ in range(100):
            if done.exists():
                break
            time.sleep(0.05)
        self.assertEqual(done.read_text().strip(), "0")
        self.assertIsNone(proc.poll())  # still waiting for Enter
        proc.kill()

    def test_closing_the_window_mid_install_reports_aborted(self):
        proc, done = self._run("sleep 30", wait=False)
        time.sleep(0.5)
        os.killpg(proc.pid, signal.SIGHUP)  # what closing a terminal does
        proc.wait(timeout=10)
        self.assertEqual(done.read_text().strip(), "aborted")

    def test_paths_with_spaces_and_quotes_are_safe(self):
        fake_bin(self.bin, "xterm", 'shift\nexec "$@"\n')
        odd = self.bin / "it's a dir"
        odd.mkdir()
        done = odd / "done"
        proc = terminal.open_terminal("true", done_file=str(done))
        proc.wait(timeout=10)
        self.assertEqual(done.read_text().strip(), "0")

    def test_launcher_survives_a_terminal_that_cannot_start(self):
        fake_bin(self.bin, "xterm", "exit 3\n")
        proc = terminal.open_terminal("true")
        self.assertTrue(proc)  # launched; the terminal itself failing is its business
        proc.wait(timeout=10)


class MissingPackagesTests(unittest.TestCase):
    def analysis(self, *deps):
        entry = DotfileEntry(name="x", display_name="x", path="/h/x")
        return FullAnalysis(file_analyses=[FileAnalysis(entry=entry, deps=list(deps))])

    def test_canonical_ids_of_required_missing_packages(self):
        full = self.analysis(
            Dependency(package="waybar", description="", installed=False),
            Dependency(package="waybar", description="", installed=False),
            Dependency(package="fd", description="", installed=False, optional=True),
            Dependency(package="git", description="", installed=True),
            Dependency(package="i3-wm", description="", installed=False, local_name="i3"),
        )
        self.assertEqual(full.missing_packages, ["i3-wm", "waybar"])

    def test_install_command_uses_the_local_package_manager_and_names(self):
        apt = distro.MANAGERS[1]
        with mock.patch.object(distro, "detect_manager", return_value=apt):
            self.assertEqual(distro.install_command(["i3-wm", "waybar", "fd"]),
                             "sudo apt install i3-wm waybar fd-find")
        dnf = next(m for m in distro.MANAGERS if m.id == "dnf")
        with mock.patch.object(distro, "detect_manager", return_value=dnf):
            self.assertEqual(distro.install_command(["i3-wm", "waybar"]),
                             "sudo dnf install i3 waybar")

    def test_refreshing_forgets_what_was_cached_about_installed_packages(self):
        distro._installed_cache["zzz"] = False
        distro.forget_installed_cache()
        self.assertEqual(distro._installed_cache, {})


if __name__ == "__main__":
    unittest.main()
