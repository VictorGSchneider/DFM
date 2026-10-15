"""The version lives in one place and the changelog and entry points agree with it."""

import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path

import dfm
from dfm import cli

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


class VersionTests(unittest.TestCase):
    def test_version_is_semver(self):
        self.assertRegex(dfm.__version__, r"^\d+\.\d+\.\d+$")

    def test_setup_py_reads_the_version_from_the_package(self):
        source = (ROOT / "setup.py").read_text()
        self.assertNotRegex(source, r'version\s*=\s*"\d')  # no second copy to forget
        if importlib.util.find_spec("setuptools") is None:
            self.skipTest("setuptools not installed")
        out = subprocess.run([sys.executable, "setup.py", "--version"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(out.strip().splitlines()[-1], dfm.__version__)

    def test_cli_prints_the_version_without_touching_gtk(self):
        out = subprocess.run([sys.executable, "-m", "dfm", "--version"], cwd=ROOT,
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), f"dfm {dfm.__version__}")
        self.assertEqual(cli.main(["-V"]), 0)

    def test_the_console_script_points_at_the_gtk_free_entry_point(self):
        self.assertIn('"dfm=dfm.cli:main"', (ROOT / "setup.py").read_text())


class ChangelogTests(unittest.TestCase):
    def test_current_version_is_the_newest_release_in_the_changelog(self):
        released = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", CHANGELOG, re.MULTILINE)
        self.assertTrue(released)
        self.assertEqual(released[0], dfm.__version__)

    def test_every_release_has_a_date_and_a_compare_link(self):
        for version in re.findall(r"^## \[(\d+\.\d+\.\d+)\]", CHANGELOG, re.MULTILINE):
            with self.subTest(version=version):
                self.assertRegex(CHANGELOG, rf"(?m)^## \[{re.escape(version)}\] - \d{{4}}-\d\d-\d\d$")
                self.assertRegex(CHANGELOG, rf"(?m)^\[{re.escape(version)}\]: https://")
        self.assertIn("## [Unreleased]", CHANGELOG)

    def test_release_notes_script_extracts_exactly_one_section(self):
        def run(tag):
            return subprocess.run([sys.executable, "scripts/release_notes.py", tag],
                                  cwd=ROOT, capture_output=True, text=True)

        current = run(f"v{dfm.__version__}")
        self.assertEqual(current.returncode, 0, current.stderr)
        self.assertTrue(current.stdout.strip())
        self.assertNotIn("## [", current.stdout)            # didn't run into the next release
        self.assertNotIn("https://github.com", current.stdout.split("\n")[-2])  # nor the link list
        first = run("v2.0.0")
        self.assertEqual(first.returncode, 0)
        self.assertIn("First tracked release", first.stdout)
        self.assertNotIn("Missing Dependencies", first.stdout)
        missing = run("v9.9.9")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("no notes", missing.stderr)


if __name__ == "__main__":
    unittest.main()
