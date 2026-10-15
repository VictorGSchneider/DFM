"""Numbers behind the Analyzer's summary cards."""

import unittest

from dfm.core.analyzer_types import FileAnalysis, FullAnalysis, Issue, IssueSeverity
from dfm.core.dependencies import Dependency
from dfm.core.scanner import DotfileEntry


def analysis(name, *, deps=(), issues=()):
    return FileAnalysis(
        entry=DotfileEntry(name=name, display_name=name, path=f"/h/{name}"),
        deps=list(deps), issues=list(issues),
    )


def dep(package, installed, optional=False, local_name=""):
    return Dependency(package=package, description="", installed=installed,
                      optional=optional, local_name=local_name)


def issue(severity, category):
    return Issue(severity=severity, title="t", detail="d", category=category)


class SummaryTests(unittest.TestCase):
    def test_only_required_and_missing_packages_count(self):
        full = FullAnalysis(file_analyses=[analysis("a", deps=[
            dep("alacritty", installed=False),
            dep("fd", installed=False, optional=True),   # optional: not counted
            dep("git", installed=True),                  # present: not counted
        ])])
        self.assertEqual(full.missing_dependencies, ["alacritty"])

    def test_a_package_needed_by_several_dotfiles_is_listed_once(self):
        full = FullAnalysis(file_analyses=[
            analysis("hypr", deps=[dep("waybar", installed=False)]),
            analysis("waybar", deps=[dep("waybar", installed=False)]),
            analysis("sway", deps=[dep("grim", installed=False)]),
        ])
        self.assertEqual(full.missing_dependencies, ["grim", "waybar"])

    def test_names_use_the_local_package_manager_spelling(self):
        full = FullAnalysis(file_analyses=[analysis("i3", deps=[
            dep("i3-wm", installed=False, local_name="i3")])])
        self.assertEqual(full.missing_dependencies, ["i3 (i3-wm)"])

    def test_missing_packages_are_not_also_counted_as_config_errors(self):
        full = FullAnalysis(file_analyses=[analysis("a", issues=[
            issue(IssueSeverity.ERROR, "dependency"),
            issue(IssueSeverity.ERROR, "syntax"),
            issue(IssueSeverity.WARNING, "duplicate"),
        ])])
        self.assertEqual(full.config_errors, 1)
        self.assertEqual(full.total_errors, 2)  # unchanged: used per file elsewhere

    def test_nothing_missing(self):
        self.assertEqual(FullAnalysis().missing_dependencies, [])
        self.assertEqual(FullAnalysis().config_errors, 0)


if __name__ == "__main__":
    unittest.main()
