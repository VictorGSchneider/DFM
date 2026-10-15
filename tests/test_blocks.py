"""`name { ... }` blocks are sections, not editable fields."""

import os
import tempfile
import unittest

from dfm.core.parser import FieldType, parse_config, update_config_value


def parse(name: str, content: str):
    path = os.path.join(tempfile.mkdtemp(), name)
    with open(path, "w") as f:
        f.write(content)
    return path, parse_config(path).fields


def editable(fields):
    return [f for f in fields if f.field_type != FieldType.COMMENT]


class BlockTests(unittest.TestCase):
    HYPR = ("general {\n    border_size = 1\n    gaps_in = 5\n}\n"
            "decoration {\n    rounding = 4\n    blur {\n        size = 3\n    }\n"
            "    active_opacity = 0.9\n}\nmisc {\n    force_default_wallpaper = 0\n}\n")

    def test_block_openers_are_not_editable_fields(self):
        _, fields = parse("hyprland.conf", self.HYPR)
        self.assertEqual([f.key for f in editable(fields)],
                         ["border_size", "gaps_in", "rounding", "size",
                          "active_opacity", "force_default_wallpaper"])
        self.assertFalse([f for f in editable(fields) if f.value.strip() in ("{", "}")])

    def test_fields_are_grouped_under_their_block(self):
        _, fields = parse("hyprland.conf", self.HYPR)
        section = {f.key: f.section for f in editable(fields)}
        self.assertEqual(section["border_size"], "general")
        self.assertEqual(section["rounding"], "decoration")
        self.assertEqual(section["size"], "decoration > blur")
        self.assertEqual(section["active_opacity"], "decoration")
        self.assertEqual(section["force_default_wallpaper"], "misc")

    def test_rofi_selectors_and_libconfig_groups(self):
        _, fields = parse("config.rasi",
                          '* {\n    background: #101010;\n}\n'
                          'element selected.normal {\n    text-color: #fff;\n}\n')
        self.assertEqual([(f.key, f.section) for f in editable(fields)],
                         [("background", "*"), ("text-color", "element selected.normal")])
        _, fields = parse("picom.conf", 'blur: {\n  method = "dual_kawase";\n};\nshadow = true;\n')
        self.assertEqual([(f.key, f.section) for f in editable(fields)],
                         [("method", "blur"), ("shadow", "General")])

    def test_i3_mode_block(self):
        _, fields = parse("config", 'font pango:monospace 8\nmode "resize" {\n'
                                    "    bindsym h resize shrink width 10px\n}\nexec foo\n")
        keys = [f.key for f in editable(fields)]
        self.assertNotIn("mode", keys)
        self.assertIn("bind:h", keys)
        bind = next(f for f in fields if f.key == "bind:h")
        self.assertIn("resize", bind.section)
        self.assertEqual(next(f for f in fields if f.key == "exec").section, "Autostart")

    def test_edits_still_land_on_the_right_line(self):
        path, fields = parse("hyprland.conf", self.HYPR)
        size = next(f for f in fields if f.key == "size")
        self.assertTrue(update_config_value(path, size, "9"))
        with open(path) as f:
            self.assertEqual(f.read(), self.HYPR.replace("size = 3", "size = 9"))

    def test_opening_of_a_multiline_array_is_not_editable(self):
        content = 'shadow-exclude = [\n  "a",\n  "b"\n];\nshadow = true;\n'
        path, fields = parse("picom.conf", content)
        opener = next(f for f in fields if f.key == "shadow-exclude")
        self.assertFalse(update_config_value(path, opener, "oops"))
        with open(path) as f:
            self.assertEqual(f.read(), content)


if __name__ == "__main__":
    unittest.main()
