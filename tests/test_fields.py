"""Regression tests for value handling behind the editable field widgets."""

import os
import tempfile
import unittest

from dfm.core.parser import FieldType, parse_config, update_config_value
from dfm.core.parser.colors import format_color, parse_color
from dfm.core.parser.infer import infer_field_type
from dfm.core.parser.toggles import toggle_value


class ToggleTests(unittest.TestCase):
    def test_style_of_the_existing_value_is_kept(self):
        cases = [
            ("true", True, "true"), ("true", False, "false"),
            ("yes", False, "no"), ("no", True, "yes"),
            ("on", False, "off"), ("off", True, "on"),
            ("1", False, "0"), ("0", True, "1"),
            ("enabled", False, "disabled"), ("disabled", True, "enabled"),
            ("enable", False, "disable"),
            ("True", False, "False"), ("YES", False, "NO"), ("Off", True, "On"),
        ]
        for old, active, expected in cases:
            with self.subTest(old=old, active=active):
                self.assertEqual(toggle_value(old, active), expected)

    def test_unknown_old_value_falls_back_to_true_false(self):
        self.assertEqual(toggle_value("", True), "true")
        self.assertEqual(toggle_value("maybe", False), "false")


class ColorTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_color("#ff0000"), (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(parse_color("#f00"), (1.0, 0.0, 0.0, 1.0))
        r, g, b, a = parse_color("#00ff0080")
        self.assertEqual((r, g, b), (0.0, 1.0, 0.0))
        self.assertAlmostEqual(a, 128 / 255)
        self.assertEqual(parse_color("rgba(ff000000)"), (1.0, 0.0, 0.0, 0.0))  # hyprland
        self.assertEqual(parse_color("rgb(00ff00)"), (0.0, 1.0, 0.0, 1.0))      # hyprland
        self.assertEqual(parse_color("rgb(255, 0, 0)"), (1.0, 0.0, 0.0, 1.0))   # css
        self.assertEqual(parse_color("rgba(0, 0, 255, 0.5)"), (0.0, 0.0, 1.0, 0.5))
        self.assertIsNone(parse_color("nonsense"))
        self.assertIsNone(parse_color("rgba(33ccffee) rgba(00ff99ee) 45deg"))

    def test_format_keeps_the_original_syntax(self):
        red = (1.0, 0.0, 0.0, 1.0)
        self.assertEqual(format_color("#00ff00", *red), "#ff0000")
        self.assertEqual(format_color("#00f", *red), "#ff0000")
        self.assertEqual(format_color("#00ff0080", 1.0, 0.0, 0.0, 128 / 255), "#ff000080")
        self.assertEqual(format_color("rgba(33ccffee)", 1.0, 0.0, 0.0, 238 / 255), "rgba(ff0000ee)")
        self.assertEqual(format_color("rgb(00ff00)", *red), "rgb(ff0000)")
        self.assertEqual(format_color("rgb(0, 255, 0)", *red), "rgb(255, 0, 0)")
        self.assertEqual(format_color("rgba(0, 0, 255, 0.5)", 1.0, 0.0, 0.0, 0.5), "rgba(255, 0, 0, 0.5)")
        self.assertEqual(format_color("whatever", *red), "#ff0000")


class InferTests(unittest.TestCase):
    def test_gradients_and_color_lists_are_not_single_colors(self):
        for value in ("rgba(33ccffee) rgba(00ff99ee) 45deg", "rgba(a) rgba(b)"):
            with self.subTest(value=value):
                self.assertNotEqual(infer_field_type("col.active_border", value), FieldType.COLOR)

    def test_single_colors_are_colors(self):
        for value in ("#fff", "#102030", "#10203040", "rgba(33ccffee)", "rgb(1,2,3)"):
            with self.subTest(value=value):
                self.assertEqual(infer_field_type("color", value), FieldType.COLOR)

    def test_zero_and_one_are_numbers_when_the_key_is_numeric(self):
        for key in ("border_size", "gaps_in", "rounding", "blur.passes", "repeat_rate"):
            with self.subTest(key=key):
                self.assertNotEqual(infer_field_type(key, "1"), FieldType.TOGGLE)
                self.assertNotEqual(infer_field_type(key, "0"), FieldType.TOGGLE)

    def test_booleans_stay_toggles(self):
        for value in ("true", "false", "yes", "no", "on", "off", "enabled"):
            self.assertEqual(infer_field_type("whatever", value), FieldType.TOGGLE)
        self.assertEqual(infer_field_type("enable_blur", "1"), FieldType.TOGGLE)


class WriterStateTests(unittest.TestCase):
    def make(self, name, content):
        path = os.path.join(tempfile.mkdtemp(), name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_changing_a_value_back_after_a_save_is_written(self):
        """The UI keeps one field object per widget and never updates its value."""
        path = self.make("a.toml", "[w]\nsize = 5\n")
        field = next(f for f in parse_config(path).fields if f.key == "w.size")
        self.assertTrue(update_config_value(path, field, "7"))
        self.assertTrue(update_config_value(path, field, "5"))
        with open(path) as f:
            self.assertEqual(f.read(), "[w]\nsize = 5\n")
        self.assertTrue(update_config_value(path, field, "9"))
        with open(path) as f:
            self.assertEqual(f.read(), "[w]\nsize = 9\n")

    def test_writing_the_same_value_leaves_the_file_untouched(self):
        path = self.make("a.toml", "size = 5 # px\n")
        before = os.stat(path).st_mtime_ns
        field = next(f for f in parse_config(path).fields if f.key == "size")
        self.assertTrue(update_config_value(path, field, "5"))
        self.assertEqual(os.stat(path).st_mtime_ns, before)

    def test_multiline_values_are_refused(self):
        path = self.make("a.conf", "k = 1\nj = 2\n")
        field = next(f for f in parse_config(path).fields if f.key == "k")
        self.assertFalse(update_config_value(path, field, "a\nb"))
        self.assertFalse(update_config_value(path, field, "a\rb"))
        with open(path) as f:
            self.assertEqual(f.read(), "k = 1\nj = 2\n")


if __name__ == "__main__":
    unittest.main()
