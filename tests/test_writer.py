"""Regression tests for parsing + writing config values back to disk."""

import os
import tempfile
import unittest

from dfm.core.parser import FieldType, parse_config, update_config_value


def _write(name: str, content: str) -> str:
    d = tempfile.mkdtemp()
    path = os.path.join(d, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return path


def _field(path: str, key: str):
    return next(f for f in parse_config(path).fields if f.key == key)


def _edit(name: str, content: str, key: str, value: str) -> str:
    path = _write(name, content)
    ok = update_config_value(path, _field(path, key), value)
    assert ok, f"update refused for {key!r}"
    with open(path) as f:
        return f.read()


class RoundTripTests(unittest.TestCase):
    """Edit every field to something else and back: the file must be unchanged."""

    CASES = {
        ".bashrc": 'export EDITOR=vim\nexport P="a b"\nalias ll="ls -la"\n'
                   "alias g='git'\nsource ~/x.sh\nPATH=$PATH:~/bin\n"
                   "setopt autocd\nunsetopt beep\nset -o vi\n",
        "a.toml": '# c\n\n[font]\nsize = 11.0\nname = "Mono"\n\n[window]\n'
                  'opacity = 0.9 # inline\ndecor = true\n',
        "a.yaml": "a: 1\nb:\n  c: true\n  d: 'q'\n  e: \"w\"\n",
        "a.json": '{\n  "x": 1,\n  "y": "s",\n  "z": {\n    "n": true,\n    "m": null\n  }\n}\n',
        "a.ini": "[user]\n\tname = A\n\temail = \"a@b.c\"\n\n[core]\neditor = vim\n",
        ".Xresources": "! c\nXft.dpi: 96\nURxvt.font: xft:Mono:size=10\n",
        "i3/config": "set $mod Mod4\nbindsym $mod+Return exec alacritty\n"
                     "bindsym $mod+q kill\nfont pango:monospace 8\nfloating_modifier $mod\n",
    }

    def test_edit_and_restore_is_byte_identical(self):
        for name, content in self.CASES.items():
            path = _write(name, content)
            for field in parse_config(path).fields:
                if field.field_type == FieldType.COMMENT or field.value == "null":
                    continue  # null -> text -> null loses the type, by nature
                with self.subTest(file=name, key=field.key):
                    with open(path, "w") as f:
                        f.write(content)
                    numeric = field.value.replace(".", "", 1).isdigit()
                    flipped = {"true": "false", "false": "true"}.get(
                        field.value, "7" if numeric else "zz9")
                    self.assertTrue(update_config_value(path, field, flipped))
                    with open(path) as f:
                        self.assertNotEqual(f.read(), content)
                    changed = next(f for f in parse_config(path).fields
                                   if f.line_number == field.line_number)
                    self.assertEqual(changed.value, flipped)
                    self.assertTrue(update_config_value(path, changed, field.value))
                    with open(path) as f:
                        self.assertEqual(f.read(), content)


class EditTests(unittest.TestCase):
    def test_toml_edit_hits_the_right_line_with_blank_lines_and_comments(self):
        content = ("# my config\n\n[font]\nsize = 11.0\n\n# window\n"
                   "[window]\nopacity = 0.9\ndecor = true\n")
        out = _edit("a.toml", content, "window.opacity", "0.5")
        self.assertEqual(out, content.replace("opacity = 0.9", "opacity = 0.5"))

    def test_toml_same_key_in_two_tables(self):
        content = "[a]\nsize = 1\n[b]\nsize = 2\n"
        out = _edit("a.toml", content, "b.size", "9")
        self.assertEqual(out, "[a]\nsize = 1\n[b]\nsize = 9\n")

    def test_toml_keeps_quotes_and_inline_comment(self):
        out = _edit("a.toml", 'name = "Mono" # f\nsize = 3 # px\n', "name", "Fira")
        self.assertEqual(out, 'name = "Fira" # f\nsize = 3 # px\n')
        out = _edit("a.toml", 'name = "Mono" # f\nsize = 3 # px\n', "size", "4")
        self.assertEqual(out, 'name = "Mono" # f\nsize = 4 # px\n')

    def test_yaml_nested_edit(self):
        content = "top: 1\n\n# c\nnet:\n  port: 80\n  host: 'a'\nother:\n  port: 5\n"
        out = _edit("a.yaml", content, "other.port", "6")
        self.assertEqual(out, content.replace("port: 5", "port: 6"))
        out = _edit("a.yaml", content, "net.host", "b")
        self.assertEqual(out, content.replace("'a'", "'b'"))

    def test_json_edit(self):
        content = '{\n  "x": 1,\n  "y": "s",\n  "z": {\n    "n": true\n  }\n}\n'
        out = _edit("a.json", content, "x", "2")
        self.assertEqual(out, content.replace('"x": 1', '"x": 2'))
        out = _edit("a.json", content, "y", 'he said "hi"')
        self.assertEqual(out, content.replace('"s"', '"he said \\"hi\\""'))
        out = _edit("a.json", content, "z.n", "false")
        self.assertEqual(out, content.replace("true", "false"))

    def test_json_one_line_object_is_refused_not_corrupted(self):
        path = _write("a.json", '{"x": 1, "y": 2}\n')
        self.assertFalse(update_config_value(path, _field(path, "y"), "3"))
        with open(path) as f:
            self.assertEqual(f.read(), '{"x": 1, "y": 2}\n')

    def test_shell_alias_and_source_keep_their_keyword(self):
        content = 'alias ll="ls -la"\nsource ~/a.sh\n'
        out = _edit(".bashrc", content, "alias:ll", "ls -lah")
        self.assertEqual(out, 'alias ll="ls -lah"\nsource ~/a.sh\n')
        out = _edit(".bashrc", content, "source:a.sh", "~/b.sh")
        self.assertEqual(out, 'alias ll="ls -la"\nsource ~/b.sh\n')

    def test_shell_options_toggle(self):
        content = "setopt autocd\nunsetopt beep\nset -o vi\n"
        self.assertEqual(_edit(".bashrc", content, "autocd", "false"),
                         "unsetopt autocd\nunsetopt beep\nset -o vi\n")
        self.assertEqual(_edit(".bashrc", content, "beep", "true"),
                         "setopt autocd\nsetopt beep\nset -o vi\n")
        self.assertEqual(_edit(".bashrc", content, "vi", "false"),
                         "setopt autocd\nunsetopt beep\nset +o vi\n")

    def test_shell_value_with_spaces_gets_quoted(self):
        out = _edit(".bashrc", "export A=x\n", "A", "a b")
        self.assertEqual(out, 'export A="a b"\n')

    def test_i3_bindsym_keeps_key_combo(self):
        content = "bindsym $mod+Return exec alacritty\nset $mod Mod4\n"
        out = _edit("i3/config", content, "bind:$mod+Return", "exec foot")
        self.assertEqual(out, "bindsym $mod+Return exec foot\nset $mod Mod4\n")

    def test_readback_matches_what_was_written(self):
        for name, content, key in [
            ("a.toml", "[w]\nopacity = 0.9\n", "w.opacity"),
            ("a.yaml", "a:\n  b: 1\n", "a.b"),
            ("a.json", '{\n  "a": {\n    "b": 1\n  }\n}\n', "a.b"),
            (".bashrc", "alias ll='ls'\n", "alias:ll"),
        ]:
            with self.subTest(file=name):
                path = _write(name, content)
                self.assertTrue(update_config_value(path, _field(path, key), "7"))
                self.assertEqual(_field(path, key).value, "7")

    def test_stale_line_is_refused_if_file_changed_underneath(self):
        path = _write("a.toml", "a = 1\nb = 2\n")
        field = _field(path, "b")
        with open(path, "w") as f:
            f.write("a = 1\nc = 3\n")  # another key now sits on b's recorded line
        self.assertFalse(update_config_value(path, field, "9"))
        with open(path) as f:
            self.assertEqual(f.read(), "a = 1\nc = 3\n")

    def test_crlf_utf8_and_symlink_are_preserved(self):
        d = tempfile.mkdtemp()
        real = os.path.join(d, "real.toml")
        link = os.path.join(d, "link.toml")
        with open(real, "wb") as f:
            f.write("n = 1\r\nname = \"caf\u00e9\"\r\n".encode())
        os.chmod(real, 0o640)
        os.symlink(real, link)
        self.assertTrue(update_config_value(link, _field(link, "n"), "2"))
        self.assertTrue(os.path.islink(link))
        with open(real, "rb") as f:
            self.assertEqual(f.read(), "n = 2\r\nname = \"caf\u00e9\"\r\n".encode())
        self.assertEqual(os.stat(real).st_mode & 0o777, 0o640)

    def test_non_utf8_bytes_survive_an_edit(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, ".bashrc")
        with open(path, "wb") as f:
            f.write(b"# caf\xe9\nexport A=1\n")
        self.assertTrue(update_config_value(path, _field(path, "A"), "2"))
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"# caf\xe9\nexport A=2\n")

class TerminatedSyntaxTests(unittest.TestCase):
    """rofi (.rasi) and picom (libconfig) end every value with ';'."""

    PICOM = 'backend = "glx";\ninactive-opacity = 0.9;\nshadow = true;\n'
    ROFI = 'configuration {\n    modi: "drun,run";\n    width: 40%;\n}\n'

    def test_values_are_read_without_quotes_or_semicolon(self):
        path = _write("picom.conf", self.PICOM)
        self.assertEqual(_field(path, "backend").value, "glx")
        self.assertEqual(_field(path, "inactive-opacity").value, "0.9")
        self.assertEqual(_field(path, "shadow").value, "true")
        path = _write("config.rasi", self.ROFI)
        self.assertEqual(_field(path, "modi").value, "drun,run")
        self.assertEqual(_field(path, "width").value, "40%")

    def test_numbers_are_recognised_despite_the_semicolon(self):
        path = _write("picom.conf", self.PICOM)
        self.assertEqual(_field(path, "inactive-opacity").field_type, FieldType.SLIDER)

    def test_edits_keep_quotes_and_semicolon(self):
        self.assertEqual(_edit("picom.conf", self.PICOM, "inactive-opacity", "0.5"),
                         self.PICOM.replace("0.9", "0.5"))
        self.assertEqual(_edit("picom.conf", self.PICOM, "backend", "xrender"),
                         self.PICOM.replace("glx", "xrender"))
        self.assertEqual(_edit("config.rasi", self.ROFI, "modi", "drun"),
                         self.ROFI.replace("drun,run", "drun"))
        self.assertEqual(_edit("config.rasi", self.ROFI, "width", "50%"),
                         self.ROFI.replace("40%", "50%"))


class JsonContainerTests(unittest.TestCase):
    CONTENT = ('{\n  "modules-left": ["a", "b"],\n  "nested": {"k": 1},\n'
               '  "tail": [1, 2]\n}\n')

    def test_single_line_array_can_be_replaced(self):
        out = _edit("a.json", self.CONTENT, "modules-left", '["x"]')
        self.assertEqual(out, self.CONTENT.replace('["a", "b"]', '["x"]'))
        out = _edit("a.json", self.CONTENT, "tail", "[3]")
        self.assertEqual(out, self.CONTENT.replace("[1, 2]", "[3]"))

    def test_invalid_json_text_is_refused(self):
        path = _write("a.json", self.CONTENT)
        self.assertFalse(update_config_value(path, _field(path, "modules-left"), "[oops"))
        with open(path) as f:
            self.assertEqual(f.read(), self.CONTENT)

    def test_multiline_array_is_refused(self):
        content = '{\n  "a": [\n    1,\n    2\n  ]\n}\n'
        path = _write("a.json", content)
        self.assertFalse(update_config_value(path, _field(path, "a"), "[3]"))
        with open(path) as f:
            self.assertEqual(f.read(), content)


if __name__ == "__main__":
    unittest.main()
