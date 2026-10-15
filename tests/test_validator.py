"""Regression tests for syntax validation (no false alarms, real errors kept)."""

import os
import tempfile
import unittest

from dfm.core.validator import validate_file


def check(name: str, content: str):
    path = os.path.join(tempfile.mkdtemp(), name)
    with open(path, "w") as f:
        f.write(content)
    return validate_file(path)


class JsonTests(unittest.TestCase):
    def test_urls_in_strings_are_not_comments(self):
        self.assertTrue(check("a.json", '{"url": "https://example.com/x", "n": 1}').valid)

    def test_comments_are_allowed_but_not_inside_strings(self):
        content = '{\n  // comment\n  "a": 1, /* c */ "b": "x//y /* z */"\n}\n'
        self.assertTrue(check("a.json", content).valid)

    def test_real_syntax_error_is_reported_with_position(self):
        result = check("a.json", '{\n  "a": 1,\n  "b": \n}\n')
        self.assertFalse(result.valid)
        self.assertIn("line", result.errors[0])

    def test_error_line_numbers_survive_comment_stripping(self):
        result = check("a.json", '{\n  // one\n  /* two\n  three */\n  "a": }\n')
        self.assertFalse(result.valid)
        self.assertIn("line 5", result.errors[0])


class YamlTests(unittest.TestCase):
    def test_multi_document_stream_is_valid(self):
        self.assertTrue(check("a.yaml", "a: 1\n---\nb: 2\n").valid)

    def test_bad_yaml_is_still_invalid(self):
        self.assertFalse(check("a.yaml", "a: [1, 2\nb: 3\n").valid)


class ShellTests(unittest.TestCase):
    def warnings(self, content):
        return check(".bashrc", content).warnings

    def test_apostrophe_inside_double_quotes_or_comment(self):
        self.assertEqual(self.warnings('alias x="it\'s"\nexport A=1 # don\'t\n'), [])

    def test_case_statement_parentheses(self):
        self.assertEqual(self.warnings(
            "case $1 in\n  start) echo s ;;\n  a|b) echo t ;;\n  *) echo u ;;\nesac\n"), [])

    def test_parameter_length_is_not_a_comment(self):
        self.assertEqual(self.warnings("n=${#arr[@]}\nif [ $n -gt 0 ]; then echo hi; fi\n"), [])

    def test_heredoc_body_is_not_code(self):
        self.assertEqual(self.warnings("cat <<EOF\nit's (here\nEOF\necho ok\n"), [])

    def test_multiline_string_is_fine(self):
        self.assertEqual(self.warnings('msg="line one\nline two"\necho "$msg"\n'), [])

    def test_unterminated_quote_is_reported_with_its_line(self):
        found = self.warnings('echo ok\necho "oops\necho more\n')
        self.assertEqual(len(found), 1)
        self.assertIn("2", found[0])

    def test_unbalanced_brace_is_reported(self):
        self.assertTrue(any("braces" in w.lower() for w in self.warnings("f() {\n  echo hi\n")))


if __name__ == "__main__":
    unittest.main()
