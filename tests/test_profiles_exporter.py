"""Regression tests for profiles and import/export."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dfm.core import backup, exporter, profiles
from dfm.core.scanner import DotfileEntry


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        for patcher in (
            mock.patch.object(Path, "home", return_value=self.home),
            mock.patch.dict(os.environ, {"HOME": str(self.home)}),
            mock.patch.object(backup, "BACKUP_DIR", self.home / "bk"),
            mock.patch.object(profiles, "PROFILES_DIR", self.home / "pr"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def entry(self, rel="x.conf", content=b"x\n", name=None) -> DotfileEntry:
        path = self.home / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return DotfileEntry(name=name or path.name, display_name=path.name, path=str(path))


class ProfileTests(Sandbox):
    def test_deleting_an_empty_name_does_not_wipe_every_profile(self):
        e = self.entry()
        profiles.save_profile("work", "", [e])
        profiles.save_profile("home", "", [e])
        self.assertFalse(profiles.delete_profile(""))
        self.assertEqual(sorted(p.name for p in profiles.list_profiles()), ["home", "work"])

    def test_saving_an_empty_name_is_rejected(self):
        with self.assertRaises(ValueError):
            profiles.save_profile("", "", [self.entry()])

    def test_names_that_sanitize_alike_stay_separate(self):
        e = self.entry()
        profiles.save_profile("a b", "one", [e])
        profiles.save_profile("a_b", "two", [e])
        found = {p.name: p.description for p in profiles.list_profiles()}
        self.assertEqual(found, {"a b": "one", "a_b": "two"})
        self.assertTrue(profiles.delete_profile("a b"))
        self.assertEqual([p.name for p in profiles.list_profiles()], ["a_b"])

    def test_resaving_a_profile_replaces_it(self):
        e = self.entry()
        profiles.save_profile("work", "old", [e])
        profiles.save_profile("work", "new", [e])
        self.assertEqual([(p.name, p.description) for p in profiles.list_profiles()],
                         [("work", "new")])

    def test_export_survives_non_utf8_snapshot(self):
        e = self.entry(content=b"caf\xe9\n")
        profiles.save_profile("lat", "", [e])
        data = json.loads(profiles.export_profile_json("lat"))
        self.assertIn("caf", data["config_contents"][e.name])

    def test_load_restores_config_and_backs_up_current(self):
        e = self.entry(content=b"saved\n")
        profiles.save_profile("p", "", [e])
        Path(e.path).write_bytes(b"changed\n")
        profiles.load_profile("p", [e])
        self.assertEqual(Path(e.path).read_bytes(), b"saved\n")
        self.assertEqual(len(backup.get_backups(e.path)), 1)


class ExporterTests(Sandbox):
    def nvim(self) -> DotfileEntry:
        d = self.home / ".config" / "nvim"
        d.mkdir(parents=True)
        (d / "init.lua").write_text("x")
        os.symlink("/nonexistent/target", d / "dangling")
        return DotfileEntry(name="nvim", display_name="Neovim", path=str(d),
                            is_directory=True, config_file=str(d / "init.lua"))

    def test_dangling_symlink_inside_a_config_dir_does_not_abort_export(self):
        out = tempfile.mkdtemp()
        entry = self.nvim()
        folder = exporter.export_dotfiles([entry], out, "directory")
        self.assertTrue(os.path.isfile(os.path.join(folder, ".config/nvim/init.lua")))
        archive = exporter.export_dotfiles([entry], out)
        self.assertTrue(os.path.isfile(archive))

    def test_import_backs_up_files_it_overwrites_inside_directories(self):
        src = Path(tempfile.mkdtemp())
        (src / ".config/nvim").mkdir(parents=True)
        (src / ".config/nvim/init.lua").write_text("NEW")
        (src / "dfm_manifest.json").write_text(json.dumps({"entries": [{
            "name": "nvim", "display_name": "Neovim", "path": ".config/nvim",
            "is_directory": True, "enabled": True}]}))
        mine = self.home / ".config/nvim/init.lua"
        mine.parent.mkdir(parents=True)
        mine.write_text("MY PRECIOUS CONFIG")

        exporter.import_dotfiles(str(src), str(self.home))

        self.assertEqual(mine.read_text(), "NEW")
        saved = backup.get_backups(str(mine))
        self.assertEqual(len(saved), 1)
        self.assertEqual(Path(saved[0].backup_path).read_text(), "MY PRECIOUS CONFIG")

    def test_export_uses_the_name_the_user_chose(self):
        entry = self.entry(".bashrc")
        out = Path(tempfile.mkdtemp()) / "new-dir"
        archive = exporter.export_dotfiles([entry], str(out), archive_name="mine.tar.gz")
        self.assertEqual(archive, str(out / "mine.tar.gz"))
        self.assertTrue((out / "mine.tar.gz").is_file())

    def test_export_adds_the_extension_when_missing(self):
        entry = self.entry(".bashrc")
        out = tempfile.mkdtemp()
        archive = exporter.export_dotfiles([entry], out, archive_name="mydots")
        self.assertEqual(os.path.basename(archive), "mydots.tar.gz")
        self.assertTrue(os.path.isfile(archive))

    def test_exported_archive_round_trips(self):
        entry = self.entry(".bashrc", b"export A=1\n")
        archive = exporter.export_dotfiles([entry], tempfile.mkdtemp(), archive_name="a.tar.gz")
        target = Path(tempfile.mkdtemp())
        actions = exporter.import_dotfiles(archive, str(target))
        self.assertEqual([a["status"] for a in actions], ["done"])
        self.assertEqual((target / ".bashrc").read_bytes(), b"export A=1\n")

    def test_importing_something_that_is_not_an_archive_raises(self):
        bogus = self.home / "notes.txt"
        bogus.write_text("hello")
        with self.assertRaises(ValueError):
            exporter.import_dotfiles(str(bogus), str(self.home))

    def test_import_rejects_paths_that_escape_home(self):
        src = Path(tempfile.mkdtemp())
        (src / "evil").write_text("x")
        (src / "dfm_manifest.json").write_text(json.dumps({"entries": [
            {"name": "e", "path": "../escaped", "is_directory": False},
            {"name": "f", "path": "/etc/hostname", "is_directory": False}]}))
        self.assertEqual(exporter.import_dotfiles(str(src), str(self.home), dry_run=True), [])


if __name__ == "__main__":
    unittest.main()
