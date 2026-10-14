"""Regression tests for scanning and keeping the per-dotfile enabled state."""

import os
import tempfile
import unittest

from dfm.core.scanner import DotfileEntry, carry_over_enabled, scan_dotfiles


def entry(name, path=None, enabled=True):
    return DotfileEntry(name=name, display_name=name, path=path or f"/h/{name}", enabled=enabled)


class CarryOverTests(unittest.TestCase):
    def test_disabled_entries_stay_disabled_after_a_rescan(self):
        old = [entry(".bashrc", enabled=False), entry("i3", enabled=True)]
        new = [entry(".bashrc"), entry("i3")]
        carry_over_enabled(new, old)
        self.assertEqual([e.enabled for e in new], [False, True])

    def test_new_entries_default_to_enabled_and_vanished_ones_are_ignored(self):
        old = [entry("gone", enabled=False)]
        new = [entry("fresh")]
        carry_over_enabled(new, old)
        self.assertTrue(new[0].enabled)

    def test_same_name_in_different_places_is_kept_apart(self):
        old = [entry("config", "/h/a/config", enabled=False), entry("config", "/h/b/config")]
        new = [entry("config", "/h/a/config"), entry("config", "/h/b/config")]
        carry_over_enabled(new, old)
        self.assertEqual([e.enabled for e in new], [False, True])


class ScanTests(unittest.TestCase):
    def test_scan_finds_dotfiles_and_config_dirs(self):
        home = tempfile.mkdtemp()
        for rel, text in {".bashrc": "x", ".config/i3/config": "y",
                          ".config/alacritty/alacritty.toml": "z"}.items():
            path = os.path.join(home, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(text)
        found = {e.name for e in scan_dotfiles(home)}
        self.assertEqual(found, {".bashrc", "i3", "alacritty"})

    def test_broken_symlinks_and_unreadable_dirs_do_not_crash_the_scan(self):
        home = tempfile.mkdtemp()
        os.symlink("/nonexistent", os.path.join(home, ".bashrc"))
        os.makedirs(os.path.join(home, ".config", "kitty"))
        os.symlink("/nonexistent", os.path.join(home, ".config", "kitty", "kitty.conf"))
        self.assertEqual(scan_dotfiles(home), [])


if __name__ == "__main__":
    unittest.main()
