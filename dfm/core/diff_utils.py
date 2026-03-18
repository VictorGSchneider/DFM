"""Diff utilities for viewing changes before save/push/pull."""

import difflib
import os


def file_diff(path_a: str, path_b: str,
              label_a: str = "old", label_b: str = "new") -> str:
    """Generate unified diff between two files."""
    try:
        with open(path_a) as f:
            lines_a = f.readlines()
    except OSError:
        lines_a = []

    try:
        with open(path_b) as f:
            lines_b = f.readlines()
    except OSError:
        lines_b = []

    diff = difflib.unified_diff(
        lines_a, lines_b,
        fromfile=label_a,
        tofile=label_b,
    )
    return "".join(diff)


def content_diff(old_content: str, new_content: str,
                 label_a: str = "old", label_b: str = "new") -> str:
    """Generate unified diff between two strings."""
    diff = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=label_a,
        tofile=label_b,
    )
    return "".join(diff)


def diff_stats(diff_text: str) -> tuple[int, int]:
    """Count additions and deletions from a unified diff.

    Returns (additions, deletions).
    """
    adds = 0
    dels = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            adds += 1
        elif line.startswith("-") and not line.startswith("---"):
            dels += 1
    return adds, dels


def repo_diff_summary(repo_path: str,
                      entries: list) -> list[dict]:
    """Compare local dotfiles against their repo copies.

    Returns list of dicts with keys: name, display_name, status, diff, adds, dels.
    status is one of: "unchanged", "modified", "new", "deleted"
    """
    results = []

    for entry in entries:
        if not entry.enabled:
            continue

        config_path = entry.get_config_path()
        if not config_path or not os.path.isfile(config_path):
            continue

        # Determine the repo counterpart path
        from pathlib import Path
        home = str(Path.home())
        if config_path.startswith(home):
            rel = os.path.relpath(config_path, home)
        else:
            rel = os.path.basename(config_path)

        repo_file = os.path.join(repo_path, rel)

        if not os.path.isfile(repo_file):
            results.append({
                "name": entry.name,
                "display_name": entry.display_name,
                "status": "new",
                "diff": "",
                "adds": 0,
                "dels": 0,
            })
            continue

        diff_text = file_diff(repo_file, config_path,
                              label_a="repo", label_b="local")

        if not diff_text:
            results.append({
                "name": entry.name,
                "display_name": entry.display_name,
                "status": "unchanged",
                "diff": "",
                "adds": 0,
                "dels": 0,
            })
        else:
            adds, dels = diff_stats(diff_text)
            results.append({
                "name": entry.name,
                "display_name": entry.display_name,
                "status": "modified",
                "diff": diff_text,
                "adds": adds,
                "dels": dels,
            })

    return results


def format_diff_stats(adds: int, dels: int) -> str:
    """Format diff stats as a readable string."""
    parts = []
    if adds:
        parts.append(f"+{adds}")
    if dels:
        parts.append(f"-{dels}")
    return " ".join(parts) if parts else "no changes"
