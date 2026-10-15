"""Using a dotfiles repo that already exists, is already cloned and already has data."""

import os
from pathlib import Path
from unittest import mock

from dfm.core.diff_utils import repo_diff_summary
from dfm.core.github_sync import (
    find_existing_repos, get_repo_path, inspect_repo, pull_dotfiles, pull_preview,
    push_dotfiles, use_existing_repo,
)
from dfm.core.github_sync.layout import detect_layout, repo_files, repo_rel
from dfm.core.scanner import DotfileEntry
from tests.test_github_sync import Sandbox

IDENTITY = {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@e.st",
            "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@e.st"}


class ExistingRepoSandbox(Sandbox):
    def clone_with(self, files: dict[str, str], name: str = "mydots") -> Path:
        """A clone of a remote that already holds `files` (path -> content)."""
        bare = self.home / "remote.git"
        self.git("init", "-q", "--bare", "-b", "main", str(bare))
        seed = self.home / "seed"
        self.git("clone", "-q", str(bare), str(seed))
        self.git("checkout", "-q", "-b", "main", cwd=seed)
        for rel, content in files.items():
            path = seed / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        self.git("add", "-A", cwd=seed)
        self.git("commit", "-q", "-m", "seed", cwd=seed, identity=True)
        self.git("push", "-q", "-u", "origin", "main", cwd=seed)
        work = self.home / name
        self.git("clone", "-q", "-b", "main", str(bare), str(work))
        return work

    def env_identity(self):
        patcher = mock.patch.dict(os.environ, IDENTITY)
        patcher.start()
        self.addCleanup(patcher.stop)


class UseExistingRepoTests(ExistingRepoSandbox):
    def test_a_clone_with_data_is_accepted_and_remembered(self):
        work = self.clone_with({".bashrc": "a\n", ".config/nvim/init.lua": "b\n",
                                "install.sh": "#!/bin/sh\n"})
        result = use_existing_repo(str(work))
        self.assertTrue(result.success, result.message)
        self.assertEqual(get_repo_path(), str(work))
        text = "\n".join(result.details)
        self.assertIn("remote.git", text)
        self.assertIn("Branch: main", text)
        self.assertIn("Layout: mirror", text)
        self.assertIn("Dotfiles in it: 2", text)  # install.sh is not a dotfile

    def test_it_works_without_gh(self):
        work = self.clone_with({".bashrc": "a\n"})
        with mock.patch("shutil.which", return_value=None):
            self.assertTrue(use_existing_repo(str(work)).success)

    def test_a_folder_that_is_not_a_repo_is_refused(self):
        plain = self.home / "plain"
        plain.mkdir()
        result = use_existing_repo(str(plain))
        self.assertFalse(result.success)
        self.assertIn("not a git repository", result.message)
        self.assertEqual(get_repo_path(), "")

    def test_a_missing_folder_is_refused(self):
        self.assertFalse(use_existing_repo(str(self.home / "nope")).success)

    def test_a_subfolder_of_a_repo_points_at_the_root(self):
        work = self.clone_with({"sub/.bashrc": "a\n"})
        result = inspect_repo(str(work / "sub"))
        self.assertFalse(result.success)
        self.assertIn(str(work), result.message)

    def test_uncommitted_changes_are_mentioned(self):
        work = self.clone_with({".bashrc": "a\n"})
        (work / ".bashrc").write_text("edited\n")
        self.assertIn("uncommitted", "\n".join(inspect_repo(str(work)).details))

    def test_a_repo_without_a_remote_still_works_locally(self):
        work = self.home / "local"
        self.git("init", "-q", str(work))
        result = inspect_repo(str(work))
        self.assertTrue(result.success, result.message)
        self.assertIn("none", result.details[0])

    def test_common_locations_are_found(self):
        self.clone_with({".bashrc": "a\n"}, name=".dotfiles")
        self.assertEqual(find_existing_repos(), [str(self.home / ".dotfiles")])


class LayoutTests(ExistingRepoSandbox):
    def test_mirror_and_stow_are_told_apart(self):
        mirror = self.clone_with({".bashrc": "a\n"})
        self.assertEqual(detect_layout(str(mirror)), "mirror")
        stow = self.home / "stow"
        (stow / "zsh").mkdir(parents=True)
        (stow / "zsh" / ".zshrc").write_text("z\n")
        self.assertEqual(detect_layout(str(stow)), "stow")

    def test_an_empty_repo_is_mirror(self):
        empty = self.home / "empty"
        empty.mkdir()
        self.assertEqual(detect_layout(str(empty)), "mirror")

    def test_only_dotfiles_are_listed_not_scripts_or_repo_furniture(self):
        work = self.clone_with({
            ".bashrc": "a\n", ".config/x/y.conf": "b\n", "README.md": "r",
            "install.sh": "s", "scripts/setup.py": "p", ".github/ci.yml": "c",
            ".gitignore": "g"})
        self.assertEqual({home for _, home in repo_files(str(work))},
                         {".bashrc", ".config/x/y.conf"})

    def test_stow_packages_map_to_home_paths(self):
        stow = self.home / "stow"
        for rel in ("zsh/.zshrc", "zsh/README", "hypr/.config/hypr/hyprland.conf"):
            (stow / rel).parent.mkdir(parents=True, exist_ok=True)
            (stow / rel).write_text("x\n")
        self.assertEqual(
            sorted(repo_files(str(stow))),
            [("hypr/.config/hypr/hyprland.conf", ".config/hypr/hyprland.conf"),
             ("zsh/.zshrc", ".zshrc")])

    def test_a_tracked_file_keeps_its_package_and_a_new_one_goes_to_dfm(self):
        stow = self.home / "stow"
        (stow / "zsh").mkdir(parents=True)
        (stow / "zsh" / ".zshrc").write_text("z\n")
        self.assertEqual(repo_rel(str(stow), ".zshrc"), "zsh/.zshrc")
        self.assertEqual(repo_rel(str(stow), ".vimrc"), "dfm/.vimrc")


class PullIntoExistingRepoTests(ExistingRepoSandbox):
    def test_pull_leaves_scripts_and_readmes_out_of_home(self):
        work = self.clone_with({".bashrc": "from repo\n", ".config/a/b": "b\n",
                                "install.sh": "s", "README.md": "r",
                                "scripts/x": "x", ".github/ci.yml": "c"})
        use_existing_repo(str(work))
        result = pull_dotfiles()
        self.assertTrue(result.success, result.message)
        self.assertEqual((self.home / ".bashrc").read_text(), "from repo\n")
        self.assertTrue((self.home / ".config/a/b").is_file())
        for stray in ("install.sh", "README.md", "scripts", ".github"):
            self.assertFalse((self.home / stray).exists(), stray)

    def test_pull_from_a_stow_repo_installs_into_home(self):
        work = self.clone_with({"zsh/.zshrc": "z\n", "zsh/README": "r",
                                "hypr/.config/hypr/h.conf": "h\n"})
        use_existing_repo(str(work))
        self.assertTrue(pull_dotfiles().success)
        self.assertEqual((self.home / ".zshrc").read_text(), "z\n")
        self.assertTrue((self.home / ".config/hypr/h.conf").is_file())
        self.assertFalse((self.home / "README").exists())
        self.assertFalse((self.home / "zsh").exists())

    def test_identical_files_are_neither_previewed_nor_backed_up(self):
        work = self.clone_with({".bashrc": "same\n", ".vimrc": "repo\n"})
        use_existing_repo(str(work))
        (self.home / ".bashrc").write_text("same\n")
        (self.home / ".vimrc").write_text("mine\n")
        self.assertEqual(pull_preview(str(work)), ([".vimrc"], []))
        result = pull_dotfiles()
        self.assertEqual(result.details, ["< .vimrc"])


class PushIntoExistingRepoTests(ExistingRepoSandbox):
    def entry(self, name=".bashrc", content="mine\n"):
        path = self.home / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return DotfileEntry(name=name, display_name=name, path=str(path))

    def test_push_commits_only_dfm_files_not_other_work_in_the_repo(self):
        work = self.clone_with({".bashrc": "old\n", "notes.txt": "n\n"})
        use_existing_repo(str(work))
        (work / "notes.txt").write_text("unfinished\n")       # tracked, modified
        (work / "wip.txt").write_text("new\n")                 # untracked
        self.env_identity()
        result = push_dotfiles([self.entry()], "sync")
        self.assertTrue(result.success, result.message)
        committed = self.git("show", "--name-only", "--format=", "HEAD", cwd=work).stdout.split()
        self.assertEqual(committed, [".bashrc"])
        status = self.git("status", "--porcelain", cwd=work).stdout
        self.assertIn(" M notes.txt", status)
        self.assertIn("?? wip.txt", status)

    def test_push_into_a_stow_repo_updates_the_tracked_package_file(self):
        work = self.clone_with({"zsh/.zshrc": "old\n"})
        use_existing_repo(str(work))
        self.env_identity()
        result = push_dotfiles([self.entry(".zshrc", "new\n"), self.entry(".vimrc", "v\n")])
        self.assertTrue(result.success, result.message)
        self.assertEqual((work / "zsh/.zshrc").read_text(), "new\n")
        self.assertEqual((work / "dfm/.vimrc").read_text(), "v\n")
        self.assertFalse((work / ".zshrc").exists())

    def test_nothing_changed_means_nothing_to_push(self):
        work = self.clone_with({".bashrc": "mine\n"})
        use_existing_repo(str(work))
        self.env_identity()
        result = push_dotfiles([self.entry()])
        self.assertTrue(result.success)
        self.assertIn("No changes", result.message)
        self.assertEqual(self.git("rev-list", "--count", "HEAD", cwd=work).stdout.strip(), "1")

    def test_diff_preview_compares_against_the_package_copy(self):
        work = self.clone_with({"zsh/.zshrc": "same\n"})
        entry = self.entry(".zshrc", "same\n")
        summary = repo_diff_summary(str(work), [entry])
        self.assertEqual([item["status"] for item in summary], ["unchanged"])
