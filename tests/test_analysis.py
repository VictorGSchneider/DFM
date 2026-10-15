"""Regression tests for the validator, analyzer, conflicts and diff helpers."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dfm.core import diff_utils
from dfm.core.analyzer import analyze_entry
from dfm.core.conflicts import detect_conflicts
from dfm.core.scanner import DotfileEntry
from dfm.core.validator import validate_file


class TmpHome(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        for patcher in (mock.patch.object(Path, "home", return_value=self.home),
                        mock.patch.dict(os.environ, {"HOME": str(self.home)})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def make(self, rel: str, content) -> str:
        path = self.home / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        return str(path)

    def entry(self, rel: str, content) -> DotfileEntry:
        path = self.make(rel, content)
        return DotfileEntry(name=os.path.basename(path), display_name=rel, path=path)

    def issues(self, rel: str, content, category: str):
        fa = analyze_entry(self.entry(rel, content))
        return [i for i in fa.issues if i.category == category]


class NonUtf8Tests(TmpHome):
    def test_validate_and_analyze_do_not_crash_on_latin1(self):
        path = self.make(".bashrc", b"# caf\xe9\nexport A=1\n")
        self.assertTrue(validate_file(path).valid)
        analyze_entry(DotfileEntry(name=".bashrc", display_name="b", path=path))

    def test_binary_file_does_not_crash(self):
        path = self.make("bin.dat", bytes(range(256)) * 4)
        validate_file(path)

    def test_file_diff_survives_non_utf8(self):
        a = self.make("a", b"caf\xe9\n")
        b = self.make("b", "x\n")
        self.assertIn("x", diff_utils.file_diff(a, b))


class DuplicateKeyTests(TmpHome):
    def dupes(self, rel, content):
        return [i.detail for i in self.issues(rel, content, "duplicate")]

    def test_same_key_in_different_sections_is_not_a_duplicate(self):
        self.assertEqual(self.dupes(".gitconfig", "[user]\n\tname = A\n[alias]\n\tname = b\n"), [])
        self.assertEqual(self.dupes("a/config.toml", "[font]\nsize = 1\n[window]\nsize = 2\n"), [])
        self.assertEqual(self.dupes("a/c.yaml", "net:\n  port: 80\nother:\n  port: 5\n"), [])

    def test_real_duplicate_inside_one_section_is_reported(self):
        found = self.dupes(".gitconfig", "[user]\n\tname = A\n\tname = B\n")
        self.assertEqual(len(found), 1)
        self.assertIn("'name'", found[0])

    def test_real_duplicate_at_top_level_is_reported(self):
        self.assertEqual(len(self.dupes("a.conf", "k=1\nk=2\n")), 1)

    def test_repeatable_wm_directives_are_not_duplicates(self):
        hypr = ("monitor=eDP-1,preferred,auto,1\nmonitor=HDMI-A-1,preferred,auto,1\n"
                "exec-once = waybar\nexec-once = dunst\nbind = SUPER, Q, killactive\n"
                "bind = SUPER, Return, exec, kitty\nbindm = SUPER, mouse:272, movewindow\n"
                "windowrulev2 = float, class:a\nwindowrulev2 = float, class:b\n"
                "env = A,1\nenv = B,2\n")
        self.assertEqual(self.dupes(".config/hypr/hyprland.conf", hypr), [])

    def test_same_key_in_different_braced_blocks_is_not_a_duplicate(self):
        rofi = ('window {\n    background-color: #000;\n    border-radius: 4px;\n}\n'
                'inputbar {\n    background-color: #111;\n    border-radius: 2px;\n}\n')
        self.assertEqual(self.dupes(".config/rofi/config.rasi", rofi), [])
        hypr = ("decoration {\n    blur {\n        size = 3\n    }\n"
                "    shadow {\n        size = 4\n    }\n}\n"
                "general {\n    size = 1\n}\n")
        self.assertEqual(self.dupes(".config/hypr/hyprland.conf", hypr), [])

    def test_duplicate_inside_one_braced_block_is_reported(self):
        found = self.dupes(".config/rofi/config.rasi",
                           "window {\n    color: #000;\n    color: #111;\n}\n")
        self.assertEqual(len(found), 1)

    def test_shell_branches_are_not_duplicates(self):
        content = 'if [ -n "$X" ]; then\n  export EDITOR=vim\nelse\n  export EDITOR=nano\nfi\n'
        self.assertEqual(self.dupes(".bashrc", content), [])

    def test_shell_top_level_reassignment_is_still_reported(self):
        self.assertEqual(len(self.dupes(".bashrc", "export EDITOR=vim\nexport EDITOR=nano\n")), 1)


class SourceReferenceTests(TmpHome):
    def refs(self, content):
        return [i.detail for i in self.issues(".bashrc", content, "reference")]

    def test_trailing_comment_is_not_part_of_the_path(self):
        self.make("x.sh", "")
        self.assertEqual(self.refs("source ~/x.sh # old\n"), [])

    def test_process_substitution_is_not_a_file(self):
        self.assertEqual(self.refs("source <(fzf --zsh)\n"), [])

    def test_missing_file_is_still_reported(self):
        found = self.refs("source ~/nope.sh # gone\n")
        self.assertEqual(len(found), 1)
        self.assertIn("nope.sh", found[0])
        self.assertNotIn("# gone", found[0])

    def test_quoted_path_with_spaces(self):
        self.make("my dir/x.sh", "")
        self.assertEqual(self.refs('source "$HOME/my dir/x.sh"\n'), [])


class ConflictTests(TmpHome):
    def conflicts(self, bashrc, zshrc):
        return {c.key: c for c in detect_conflicts([
            self.entry(".bashrc", bashrc), self.entry(".zshrc", zshrc)])}

    def test_commented_out_lines_are_ignored(self):
        found = self.conflicts("export EDITOR=vim\nalias ll='ls'\n",
                               "# export EDITOR=nano\n# alias ll='ls -la'\n")
        self.assertEqual(found, {})

    def test_export_without_value_does_not_swallow_next_line(self):
        found = self.conflicts("export KEEP\nalias ll='ls'\n", "export KEEP\nFOO=1\n")
        self.assertEqual(found, {})

    def test_unset_is_not_a_definition(self):
        found = self.conflicts("export FOO=1\n", "unset FOO\n")
        self.assertEqual(found, {})

    def test_real_conflicts_are_still_found(self):
        found = self.conflicts("export EDITOR=vim\nalias ll='ls'\n",
                               "export EDITOR=nano\nalias ll='ls -la'\n")
        self.assertIn("EDITOR", found)
        self.assertIn("alias:ll", found)
        self.assertIn("vim", found["EDITOR"].description)
        self.assertIn("ls -la", found["alias:ll"].description)

    def test_redefining_inside_one_file_is_not_a_cross_file_conflict(self):
        found = self.conflicts("export EDITOR=vim\nexport EDITOR=nvim\nalias ll='a'\nalias ll='b'\n",
                               "export EDITOR=nvim\nalias ll='b'\n")
        self.assertEqual(found, {})  # the last definition in each file is what counts

    def test_each_file_is_listed_once_and_with_its_effective_value(self):
        found = self.conflicts("export EDITOR=vim\nexport EDITOR=nvim\n", "export EDITOR=nano\n")
        self.assertEqual(found["EDITOR"].entries, [".bashrc", ".zshrc"])
        self.assertIn(".bashrc=nvim", found["EDITOR"].description)
        self.assertNotIn(".bashrc=vim", found["EDITOR"].description)

    def test_unreadable_encoding_is_skipped(self):
        found = self.conflicts(b"# caf\xe9\nexport A=1\n", "export A=2\n")
        self.assertIn("A", found)


class RepoDiffTests(TmpHome):
    def test_file_outside_home_is_not_compared_via_a_dotdot_path(self):
        repo = Path(tempfile.mkdtemp())
        sibling = Path(str(self.home) + "2")
        sibling.mkdir()
        (sibling / "x").write_text("1\n")
        entry = DotfileEntry(name="x", display_name="x", path=str(sibling / "x"))
        result = diff_utils.repo_diff_summary(str(repo), [entry])
        self.assertEqual(result[0]["status"], "new")


if __name__ == "__main__":
    unittest.main()
