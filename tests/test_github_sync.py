"""Regression tests for github_sync, using a fake `gh` and real git."""

import json
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from dfm.core import backup
from dfm.core.github_sync import (
    get_commit_history, import_gist, list_gists, push_dotfiles, repo_config,
    save_repo_path,
)
from dfm.core.scanner import DotfileEntry

# Mirrors the real CLI: `gh gist view/list` have no --json flag.
FAKE_GH = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, sys
    a = sys.argv[1:]
    if a[:2] == ["auth", "status"]:
        sys.exit(0)
    if "--json" in a:
        print("unknown flag: --json", file=sys.stderr)
        sys.exit(1)
    files = {"a.conf": "AAA\\n", "b.conf": "BBB\\n"}
    if a[:2] == ["gist", "view"]:
        if "--files" in a:
            print("\\n".join(files))
        elif "--filename" in a:
            sys.stdout.write(files[a[a.index("--filename") + 1]])
        else:
            sys.stdout.write("".join(files.values()))
        sys.exit(0)
    if a[:1] == ["api"] and a[1].startswith("gists"):
        print(json.dumps([{"id": "g1", "description": "d", "public": False,
                           "updated_at": "2026-01-01T00:00:00Z",
                           "files": {"a.conf": {}, "b.conf": {}}}]))
        sys.exit(0)
    sys.exit(2)
''')

# No ambient git identity: committing must fail unless a test provides one.
GIT_ENV = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
           "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "user.useConfigOnly",
           "GIT_CONFIG_VALUE_0": "true"}


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        bindir = self.home / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        env = {"HOME": str(self.home), "PATH": f"{bindir}:{os.environ['PATH']}", **GIT_ENV}
        for patcher in (
            mock.patch.object(Path, "home", return_value=self.home),
            mock.patch.dict(os.environ, env),
            mock.patch.object(backup, "BACKUP_DIR", self.home / "bk"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                    "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            os.environ.pop(var, None)

    def git(self, *args, cwd=None, identity=False):
        cmd = ["git"]
        if identity:
            cmd += ["-c", "user.name=T", "-c", "user.email=t@e.st"]
        return subprocess.run(cmd + list(args), cwd=cwd, capture_output=True,
                              text=True, check=True)

    def make_repo(self) -> str:
        bare = self.home / "remote.git"
        self.git("init", "-q", "--bare", str(bare))
        work = self.home / ".dotfiles"
        self.git("clone", "-q", str(bare), str(work))
        self.git("checkout", "-q", "-b", "main", cwd=work)
        self.git("-c", "user.name=T", "-c", "user.email=t@e.st", "commit", "-q",
                 "--allow-empty", "-m", "init", cwd=work)
        self.git("push", "-q", "-u", "origin", "main", cwd=work)
        save_repo_path(str(work))
        return str(work)

    def entry(self, content="x\n") -> DotfileEntry:
        path = self.home / ".bashrc"
        path.write_text(content)
        return DotfileEntry(name=".bashrc", display_name="bash", path=str(path))


class PushTests(Sandbox):
    def test_failed_commit_is_reported_not_swallowed(self):
        work = self.make_repo()
        result = push_dotfiles([self.entry()])  # no git identity configured
        self.assertFalse(result.success)
        self.assertIn("identity", result.message.lower())
        self.assertEqual(self.git("rev-list", "--count", "HEAD", cwd=work).stdout.strip(), "1")

    def test_push_with_identity_succeeds(self):
        self.make_repo()
        with mock.patch.dict(os.environ, {
                "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@e.st",
                "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@e.st"}):
            result = push_dotfiles([self.entry()], "msg")
        self.assertTrue(result.success, result.message)

    def test_dangling_symlink_in_a_config_dir_does_not_abort_the_copy(self):
        work = self.make_repo()
        d = self.home / ".config" / "nvim"
        d.mkdir(parents=True)
        (d / "init.lua").write_text("x")
        os.symlink("/nonexistent/target", d / "dangling")
        entry = DotfileEntry(name="nvim", display_name="nvim", path=str(d), is_directory=True)
        from dfm.core.github_sync.repo import _copy_entries_to_repo
        details = _copy_entries_to_repo([entry], str(self.home), work)
        self.assertEqual(details, ["+ .config/nvim/"])
        self.assertTrue((Path(work) / ".config/nvim/init.lua").is_file())


class HistoryTests(Sandbox):
    def test_pipes_in_a_commit_subject_do_not_shift_fields(self):
        work = self.make_repo()
        (Path(work) / "f.txt").write_text("1")
        self.git("add", "-A", cwd=work)
        self.git("commit", "-q", "-m", "fix: a | b | c", cwd=work, identity=True)
        newest = get_commit_history()[0]
        self.assertEqual(newest["message"], "fix: a | b | c")
        self.assertEqual(newest["author"], "T")
        self.assertEqual(newest["files_changed"], ["f.txt"])


class GistTests(Sandbox):
    def test_import_writes_only_the_chosen_file_not_the_whole_gist(self):
        target = str(self.home / "out" / "a.conf")
        result = import_gist("g1", target)
        self.assertTrue(result.success, result.message)
        self.assertEqual(Path(target).read_text(), "AAA\n")

    def test_import_backs_up_the_existing_target(self):
        target = self.home / "a.conf"
        target.write_text("OLD\n")
        self.assertTrue(import_gist("g1", str(target)).success)
        self.assertEqual(len(backup.get_backups(str(target))), 1)

    def test_import_into_a_relative_path_works(self):
        os.chdir(self.home)
        self.assertTrue(import_gist("g1", "a.conf").success)

    def test_list_gists_returns_the_users_gists(self):
        found = list_gists()
        self.assertEqual([g["id"] for g in found], ["g1"])
        self.assertEqual(found[0]["files"], ["a.conf", "b.conf"])


class RepoConfigTests(Sandbox):
    def cfg(self) -> Path:
        path = self.home / ".config" / "dfm" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def test_getter_has_no_side_effects(self):
        self.assertEqual(repo_config.get_repo_path(), "")
        self.assertFalse((self.home / ".config" / "dfm").exists())

    def test_corrupt_or_odd_config_files_read_as_unset(self):
        for raw in (b"{not json", b"\xff\xfe\x00", b"[1, 2]", b'"str"'):
            with self.subTest(raw=raw):
                self.cfg().write_bytes(raw)
                self.assertEqual(repo_config.get_repo_path(), "")

    def test_save_keeps_other_settings_and_replaces_garbage(self):
        self.cfg().write_text(json.dumps({"other": 1}))
        save_repo_path("/r")
        self.assertEqual(json.loads(self.cfg().read_text()), {"other": 1, "repo_path": "/r"})
        self.cfg().write_bytes(b"[1]")
        save_repo_path("/r2")
        self.assertEqual(json.loads(self.cfg().read_text()), {"repo_path": "/r2"})


if __name__ == "__main__":
    unittest.main()
