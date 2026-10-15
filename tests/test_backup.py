"""Regression tests for the backup store."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dfm.core import backup


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        patches = [
            mock.patch.object(Path, "home", return_value=self.home),
            mock.patch.object(backup, "BACKUP_DIR", self.home / "bk"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.path = str(self.home / ".bashrc")

    def _write(self, data: bytes) -> None:
        with open(self.path, "wb") as f:
            f.write(data)

    def test_backups_in_the_same_second_do_not_overwrite_each_other(self):
        contents = [b"v1\n", b"v2\n", b"v3\n"]
        for data in contents:
            self._write(data)
            backup.create_backup(self.path)
        found = backup.get_backups(self.path)
        self.assertEqual(len(found), 3)
        self.assertEqual(len({b.backup_path for b in found}), 3)
        saved = sorted(open(b.backup_path, "rb").read() for b in found)
        self.assertEqual(saved, contents)

    def test_restore_returns_the_snapshot_that_was_picked(self):
        for data in (b"v1\n", b"v2\n"):
            self._write(data)
            backup.create_backup(self.path)
        self._write(b"v3\n")
        oldest = min(backup.get_backups(self.path), key=lambda b: b.timestamp)
        self.assertTrue(backup.restore_backup(oldest))
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), b"v1\n")

    def test_unchanged_file_is_not_snapshotted_twice(self):
        self._write(b"same\n")
        first = backup.create_backup(self.path)
        second = backup.create_backup(self.path)
        self.assertEqual(first.backup_path, second.backup_path)
        self.assertEqual(len(backup.get_backups(self.path)), 1)

    def test_pruning_never_deletes_a_file_another_entry_needs(self):
        with mock.patch.object(backup, "MAX_BACKUPS_PER_FILE", 2):
            for i in range(5):
                self._write(f"v{i}\n".encode())
                backup.create_backup(self.path)
        found = backup.get_backups(self.path)
        self.assertEqual(len(found), 2)
        for b in found:
            self.assertTrue(os.path.isfile(b.backup_path))

    def test_diff_survives_non_utf8_content(self):
        self._write(b"caf\xe9\n")
        entry = backup.create_backup(self.path)
        self._write(b"caf\xe9 2\n")
        self.assertIn("caf", backup.get_diff(self.path, entry))

    def test_restore_reports_failure_instead_of_raising(self):
        self._write(b"x\n")
        entry = backup.create_backup(self.path)
        os.chmod(self.path, 0o400)
        self.addCleanup(os.chmod, self.path, 0o600)
        if os.geteuid() == 0:
            self.skipTest("root ignores file permissions")
        self.assertFalse(backup.restore_backup(entry))


if __name__ == "__main__":
    unittest.main()
