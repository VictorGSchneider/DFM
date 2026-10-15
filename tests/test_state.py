"""The enabled/disabled choice per dotfile survives restarts."""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dfm.core import state
from dfm.core.analyzer import analyze_entry
from dfm.core.scanner import DotfileEntry


class Home(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        for patcher in (mock.patch.object(Path, "home", return_value=self.home),
                        mock.patch.dict(os.environ, {"HOME": str(self.home)})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def entry(self, rel, enabled=True):
        path = self.home / rel
        return DotfileEntry(name=path.name, display_name=path.name,
                            path=str(path), enabled=enabled)


class StateTests(Home):
    def test_disabled_dotfiles_are_remembered_across_runs(self):
        first = [self.entry(".bashrc", enabled=False), self.entry(".zshrc")]
        state.remember_enabled(first)

        second = [self.entry(".bashrc"), self.entry(".zshrc")]  # a fresh scan
        state.apply_saved_enabled(second)
        self.assertEqual([e.enabled for e in second], [False, True])

    def test_reenabling_forgets_the_entry(self):
        entries = [self.entry(".bashrc", enabled=False)]
        state.remember_enabled(entries)
        entries[0].enabled = True
        state.remember_enabled(entries)
        fresh = [self.entry(".bashrc")]
        state.apply_saved_enabled(fresh)
        self.assertTrue(fresh[0].enabled)

    def test_entries_that_are_not_scanned_right_now_keep_their_choice(self):
        state.remember_enabled([self.entry(".bashrc", enabled=False)])
        state.remember_enabled([self.entry(".zshrc")])  # .bashrc missing this time
        fresh = [self.entry(".bashrc")]
        state.apply_saved_enabled(fresh)
        self.assertFalse(fresh[0].enabled)

    def test_unreadable_or_odd_state_files_read_as_nothing_disabled(self):
        path = self.home / ".local/share/dfm/state.json"
        path.parent.mkdir(parents=True)
        for raw in (b"{oops", b"\xff\xfe", b"[1]", b'{"disabled": "x"}', b'{"disabled": [1, null]}'):
            with self.subTest(raw=raw):
                path.write_bytes(raw)
                entries = [self.entry(".bashrc")]
                state.apply_saved_enabled(entries)
                self.assertTrue(entries[0].enabled)

    def test_nothing_is_written_when_nothing_changed(self):
        entries = [self.entry(".bashrc")]
        state.remember_enabled(entries)
        self.assertFalse((self.home / ".local/share/dfm/state.json").exists())
        entries[0].enabled = False
        state.remember_enabled(entries)
        saved = json.loads((self.home / ".local/share/dfm/state.json").read_text())
        self.assertEqual(saved, {"disabled": [str(self.home / ".bashrc")]})
        mtime = (self.home / ".local/share/dfm/state.json").stat().st_mtime_ns
        state.remember_enabled(entries)
        self.assertEqual((self.home / ".local/share/dfm/state.json").stat().st_mtime_ns, mtime)


class PermissionTests(Home):
    def issues(self, rel, mode):
        path = self.home / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n")
        path.chmod(mode)
        fa = analyze_entry(DotfileEntry(name=path.name, display_name=path.name, path=str(path)))
        return [i for i in fa.issues if i.category == "security"]

    def test_ssh_config_that_others_can_read_is_normal(self):
        self.assertEqual(self.issues(".ssh/config", 0o644), [])
        self.assertEqual(self.issues(".ssh/config", 0o600), [])

    def test_ssh_files_others_can_write_are_flagged(self):
        for mode in (0o666, 0o664, 0o622):
            with self.subTest(mode=oct(mode)):
                found = self.issues(".ssh/config", mode)
                self.assertEqual(len(found), 1)
                self.assertIn("chmod", found[0].fix_hint)

    def test_private_keys_must_not_be_readable_by_others(self):
        self.assertEqual(len(self.issues(".ssh/id_ed25519", 0o644)), 1)
        self.assertEqual(self.issues(".ssh/id_ed25519", 0o600), [])
        self.assertEqual(self.issues(".ssh/id_ed25519.pub", 0o644), [])

    def test_secret_files_are_still_flagged_when_world_readable(self):
        for name in (".netrc", ".pgpass", ".env"):
            with self.subTest(name=name):
                self.assertEqual(len(self.issues(name, 0o644)), 1)
                self.assertEqual(self.issues(name, 0o600), [])


if __name__ == "__main__":
    unittest.main()
