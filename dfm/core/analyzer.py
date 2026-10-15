"""Unified dotfile analyzer - syntax, references, permissions, duplicates."""

import os
import re
import shlex
import stat
from pathlib import Path

from dfm.core.parser.blocks import block_open, is_block_close
from dfm.core.parser.detect import detect_format
from dfm.core.scanner import DotfileEntry
from dfm.core.analyzer_types import (
    IssueSeverity, Issue, FileAnalysis, FullAnalysis,
)
from dfm.core.analyzer_lua import (
    is_lua, check_lua_requires, check_lua_duplicate_keys,
)
from dfm.core.validator import validate_file
from dfm.core.conflicts import detect_conflicts
from dfm.core.dependencies import get_dependencies
from dfm.core.distro import install_hint


def analyze_all(entries: list[DotfileEntry]) -> FullAnalysis:
    """Run full analysis on all dotfiles."""
    result = FullAnalysis()

    for entry in entries:
        fa = analyze_entry(entry)
        result.file_analyses.append(fa)

    result.conflicts = detect_conflicts(entries)
    return result


def analyze_entry(entry: DotfileEntry) -> FileAnalysis:
    """Analyze a single dotfile entry."""
    fa = FileAnalysis(entry=entry)
    config_path = entry.get_config_path()
    file_path = config_path or entry.path

    # 1. File existence and permissions
    _check_file_status(fa, file_path)

    if not os.path.exists(file_path):
        return fa

    # 2. Syntax validation
    fa.validation = validate_file(file_path)
    if fa.validation:
        for err in fa.validation.errors:
            fa.issues.append(Issue(
                severity=IssueSeverity.ERROR,
                title="Syntax error",
                detail=err,
                file_path=file_path,
                category="syntax",
            ))
        for warn in fa.validation.warnings:
            fa.issues.append(Issue(
                severity=IssueSeverity.WARNING,
                title="Syntax warning",
                detail=warn,
                file_path=file_path,
                category="syntax",
            ))

    # 3. Content-level checks
    try:
        with open(file_path, "r", errors="replace") as f:
            content = f.read()
    except OSError:
        return fa

    lines = content.splitlines()

    _check_broken_references(fa, lines, file_path)
    _check_duplicate_keys(fa, lines, file_path)
    _check_empty_values(fa, lines, file_path)
    _check_deprecated_patterns(fa, lines, file_path)
    _check_permissions(fa, file_path)

    # 4. Dependencies
    fa.deps = get_dependencies(entry)
    for dep in fa.deps:
        if not dep.installed and not dep.optional:
            fa.issues.append(Issue(
                severity=IssueSeverity.ERROR,
                title="Missing dependency",
                detail=f"Required package '{dep.display_name}' is not installed",
                file_path=file_path,
                category="dependency",
                fix_hint=install_hint(dep.package),
            ))
        elif not dep.installed and dep.optional:
            fa.issues.append(Issue(
                severity=IssueSeverity.INFO,
                title="Optional dependency",
                detail=f"Optional package '{dep.display_name}' ({dep.description}) not installed",
                file_path=file_path,
                category="dependency",
                fix_hint=install_hint(dep.package),
            ))

    return fa


def _check_file_status(fa: FileAnalysis, file_path: str) -> None:
    """Check file existence, broken symlinks, readability."""
    if os.path.islink(file_path):
        target = os.readlink(file_path)
        if not os.path.exists(file_path):
            fa.issues.append(Issue(
                severity=IssueSeverity.ERROR,
                title="Broken symlink",
                detail=f"Symlink points to missing target: {target}",
                file_path=file_path,
                category="file",
                fix_hint=f"rm {file_path}  # or fix the target",
            ))
            return

    if not os.path.exists(file_path):
        fa.issues.append(Issue(
            severity=IssueSeverity.ERROR,
            title="File not found",
            detail=f"Config file does not exist: {file_path}",
            file_path=file_path,
            category="file",
        ))
        return

    if not os.access(file_path, os.R_OK):
        fa.issues.append(Issue(
            severity=IssueSeverity.ERROR,
            title="Unreadable file",
            detail="File exists but cannot be read (permission denied)",
            file_path=file_path,
            category="file",
            fix_hint=f"chmod +r {file_path}",
        ))


def _check_broken_references(fa: FileAnalysis, lines: list[str],
                              file_path: str) -> None:
    """Check for source/include references to files that don't exist."""
    if is_lua(file_path):
        check_lua_requires(fa, lines, file_path)
        return

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("!"):
            continue

        # source ~/.something or . ~/.something
        match = re.match(r'^(?:source|\.)\s+(.+)', stripped)
        if match:
            ref_path = _first_word(match.group(1))
            ref_path = os.path.expandvars(os.path.expanduser(ref_path))
            # Skip anything we can't resolve statically: $VAR, $(cmd), <(cmd), `cmd`
            if ref_path and not re.search(r"[$`<>(]", ref_path) \
                    and not os.path.exists(ref_path):
                fa.issues.append(Issue(
                    severity=IssueSeverity.WARNING,
                    title="Missing sourced file",
                    detail=f"Line {i}: source '{ref_path}' — file not found",
                    file_path=file_path,
                    line_number=i,
                    category="reference",
                    fix_hint="Create the file or remove the source line",
                ))

        # include directives (common in some configs)
        match = re.match(r'^(?:include|@import)\s+(.+)', stripped)
        if match:
            ref_path = _first_word(match.group(1).rstrip("; "))
            if ref_path.startswith(("~", "/")):
                ref_path = os.path.expanduser(ref_path)
                if not os.path.exists(ref_path):
                    fa.issues.append(Issue(
                        severity=IssueSeverity.WARNING,
                        title="Missing included file",
                        detail=f"Line {i}: include '{ref_path}' — file not found",
                        file_path=file_path,
                        line_number=i,
                        category="reference",
                    ))


def _first_word(text: str) -> str:
    """First shell word of `text`: handles quotes and drops a trailing comment."""
    try:
        words = shlex.split(text, comments=True)
    except ValueError:  # unbalanced quote
        words = text.split()
    return words[0] if words else ""


# Directives that legitimately appear many times (Hyprland, sway/i3, ...)
_REPEATABLE_KEYS = re.compile(
    r"^(bind[\w\-]*|unbind[\w\-]*|windowrule\w*|layerrule|exec[\w\-]*|env|monitor|workspace|"
    r"animation|bezier|device|plugin|source|submap|wallpaper|preload|"
    r"for_window|assign|set|font|mode|output|input)$"
)


def _check_duplicate_keys(fa: FileAnalysis, lines: list[str],
                           file_path: str) -> None:
    """Detect duplicate key definitions (potential shadowing)."""
    if is_lua(file_path):
        check_lua_duplicate_keys(fa, lines, file_path)
        return

    fmt = detect_format(file_path, "\n".join(lines))
    seen_keys: dict[tuple, list[int]] = {}
    section = ""
    blocks: list[str] = []               # `name { ... }` blocks we are inside
    parents: list[tuple[int, str]] = []  # YAML-style nesting by indentation

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";", "//", "!")):
            continue
        if stripped.startswith("["):
            section = stripped  # [table] / [[array]] / [section]
            parents = []
            continue
        name = block_open(stripped)
        if name is not None:
            blocks.append(name)
            parents = []
            continue
        if is_block_close(stripped):
            if blocks:
                blocks.pop()
            parents = []
            continue

        indent = len(line) - len(line.lstrip())
        if fmt == "shell" and indent:
            continue  # inside if/case/function: branches may redefine on purpose

        # key=value or key: value or export KEY=value
        match = re.match(r'^(?:export\s+)?([\w.\-]+)\s*[=:]\s*', stripped)
        if not match:
            continue
        key = match.group(1)
        if _REPEATABLE_KEYS.match(key):
            continue

        while parents and parents[-1][0] >= indent:
            parents.pop()
        scope = (section, tuple(blocks), tuple(k for _, k in parents))
        parents.append((indent, key))
        seen_keys.setdefault((scope, key), []).append(i)

    for (_, key), line_numbers in seen_keys.items():
        if len(line_numbers) > 1:
            lines_str = ", ".join(str(n) for n in line_numbers)
            fa.issues.append(Issue(
                severity=IssueSeverity.WARNING,
                title="Duplicate key",
                detail=f"'{key}' defined {len(line_numbers)} times "
                       f"(lines {lines_str}) — later value shadows earlier",
                file_path=file_path,
                line_number=line_numbers[-1],
                category="duplicate",
            ))


def _check_empty_values(fa: FileAnalysis, lines: list[str],
                         file_path: str) -> None:
    """Detect keys with empty values that might be unintentional."""
    if is_lua(file_path):
        return  # an empty Lua assignment is a syntax error, not a style hint

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";", "//", "!", "[")):
            continue

        match = re.match(r'^(?:export\s+)?([\w.\-]+)\s*=\s*$', stripped)
        if match:
            key = match.group(1)
            fa.issues.append(Issue(
                severity=IssueSeverity.INFO,
                title="Empty value",
                detail=f"Line {i}: '{key}' has no value assigned",
                file_path=file_path,
                line_number=i,
                category="style",
            ))


def _check_deprecated_patterns(fa: FileAnalysis, lines: list[str],
                                file_path: str) -> None:
    """Check for known deprecated or problematic patterns."""
    basename = os.path.basename(file_path).lower()

    deprecated = [
        (r'\bxdg-open\b.*\&\s*$', "xdg-open in background may cause issues"),
        (r'\beval\s+\$\(ssh-agent\)', "Consider using systemd ssh-agent instead"),
    ]

    # Shell-specific
    if basename in (".bashrc", ".zshrc", ".bash_profile", ".zprofile",
                    ".profile"):
        deprecated.extend([
            (r'PATH=.*\$PATH.*\$PATH',
             "PATH appended multiple times — may grow on each shell"),
        ])

    comment_prefix = "--" if is_lua(file_path) else "#"
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith(comment_prefix):
            continue
        for pattern, message in deprecated:
            if re.search(pattern, stripped):
                fa.issues.append(Issue(
                    severity=IssueSeverity.INFO,
                    title="Pattern hint",
                    detail=f"Line {i}: {message}",
                    file_path=file_path,
                    line_number=i,
                    category="pattern",
                ))


def _check_permissions(fa: FileAnalysis, file_path: str) -> None:
    """Check for insecure permissions on sensitive files."""
    basename = os.path.basename(file_path).lower()
    parts = Path(file_path).parts

    in_ssh = any(p.lower() in (".ssh", "ssh") for p in parts[:-1])
    is_private_key = in_ssh and (
        basename.startswith("id_") and not basename.endswith(".pub")
        or basename.endswith(".pem")
    )
    is_secret = basename in {".netrc", ".pgpass", ".env", "credentials", "secrets"} \
        or any(s in file_path.lower() for s in ("credentials", "secrets"))

    try:
        mode = os.stat(file_path).st_mode
    except OSError:
        return

    if is_private_key or (is_secret and not in_ssh):
        # Nobody but the owner should be able to read these (keys: not even the group)
        others = stat.S_IROTH | stat.S_IWOTH
        if mode & (others | stat.S_IRGRP | stat.S_IWGRP if is_private_key else others):
            _insecure(fa, file_path, mode, "accessible by other users")
    elif in_ssh and mode & (stat.S_IWGRP | stat.S_IWOTH):
        # ssh refuses a config that others can write; being readable is normal
        _insecure(fa, file_path, mode, "writable by other users")


def _insecure(fa: FileAnalysis, file_path: str, mode: int, why: str) -> None:
    fa.issues.append(Issue(
        severity=IssueSeverity.WARNING,
        title="Insecure permissions",
        detail=f"Sensitive file is {why} (mode {oct(mode)[-3:]})",
        file_path=file_path,
        category="security",
        fix_hint=f"chmod 600 {file_path}",
    ))
