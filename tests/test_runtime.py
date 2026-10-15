import unittest

from dfm.core.runtime import runtime_problem


class RuntimeTests(unittest.TestCase):
    def test_new_enough_runtime_is_accepted(self):
        self.assertIsNone(runtime_problem((4, 14), (1, 5)))
        self.assertIsNone(runtime_problem((4, 12), (1, 5)))
        self.assertIsNone(runtime_problem((5, 0), (2, 0)))

    def test_old_gtk_is_explained(self):
        message = runtime_problem((4, 8), (1, 5))
        self.assertIn("GTK 4.12", message)
        self.assertIn("4.8", message)
        self.assertNotIn("libadwaita", message)

    def test_old_libadwaita_is_explained(self):
        message = runtime_problem((4, 14), (1, 2))
        self.assertIn("libadwaita 1.5", message)
        self.assertIn("1.2", message)

    def test_both_old_reports_both(self):
        message = runtime_problem((4, 6), (1, 1))
        self.assertIn("GTK", message)
        self.assertIn("libadwaita", message)


if __name__ == "__main__":
    unittest.main()
