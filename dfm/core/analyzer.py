"""Unified dotfile analyzer - syntax, references, permissions, duplicates."""

import os
import re
import stat
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from dfm.core.scanner import DotfileEntry
from dfm.core.validator import validate_file, ValidationResult
from dfm.core.conflicts import detect_conflicts, Conflict
from dfm.core.dependencies import get_dependencies, Dependency


class IssueSeverity(Enum):
    ERROR = auto()
    WARNING = auto()
    INFO = auto()


@dataclass
class Issue:
    """A single issue found during analysis."""
    severity: IssueSeverity
    title: str
    detail: str
    file_path: str = ""
    line_number: int = 0
    category: str = "general"
    fix_hint: str = ""


@dataclass
class FileAnalysis:
    """Analysis results for a single dotfile."""
    entry: DotfileEntry
    issues: list[Issue] = field(default_factory=list)
    validation: ValidationResult | None = None
    deps: list[Dependency] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.INFO)

    @property
    def has_problems(self) -> bool:
        return self.error_count > 0 or self.warning_count > 0


@dataclass
class FullAnalysis:
    """Complete analysis of all dotfiles."""
    file_analyses: list[FileAnalysis] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)

    @property
    def total_errors(self) -> int:
        return sum(a.error_count for a in self.file_analyses)

    @property
    def total_warnings(self) -> int:
        return sum(a.warning_count for a in self.file_analyses)

    @property
    def total_info(self) -> int:
        return sum(a.info_count for a in self.file_analyses)

    @property
    def healthy_count(self) -> int:
        return sum(1 for a in self.file_analyses if not a.has_problems)

    @property
    def problematic_count(self) -> int:
        return sum(1 for a in self.file_analyses if a.has_problems)


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
                detail=f"Required package '{dep.package}' is not installed",
                file_path=file_path,
                category="dependency",
                fix_hint=f"sudo pacman -S {dep.package}",
            ))
        elif not dep.installed and dep.optional:
            fa.issues.append(Issue(
                severity=IssueSeverity.INFO,
                title="Optional dependency",
                detail=f"Optional package '{dep.package}' ({dep.description}) not installed",
                file_path=file_path,
                category="dependency",
                fix_hint=f"sudo pacman -S {dep.package}",
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
    home = str(Path.home())

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("!"):
            continue

        # source ~/.something or . ~/.something
        match = re.match(r'^(?:source|\.)\s+(.+)', stripped)
        if match:
            ref_path = match.group(1).strip().strip("\"'")
            ref_path = os.path.expanduser(ref_path)
            ref_path = os.path.expandvars(ref_path)
            # Skip if it contains unresolved variables
            if "$" in ref_path or "$(command" in ref_path:
                continue
            if not os.path.exists(ref_path):
                fa.issues.append(Issue(
                    severity=IssueSeverity.WARNING,
                    title="Missing sourced file",
                    detail=f"Line {i}: source '{ref_path}' — file not found",
                    file_path=file_path,
                    line_number=i,
                    category="reference",
                    fix_hint=f"Create the file or remove the source line",
                ))

        # include directives (common in some configs)
        match = re.match(r'^(?:include|@import)\s+(.+)', stripped)
        if match:
            ref_path = match.group(1).strip().strip("\"';")
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


def _check_duplicate_keys(fa: FileAnalysis, lines: list[str],
                           file_path: str) -> None:
    """Detect duplicate key definitions (potential shadowing)."""
    seen_keys: dict[str, list[int]] = {}

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";", "//", "!", "[")):
            continue

        # key=value or key: value or export KEY=value
        match = re.match(r'^(?:export\s+)?([\w.\-]+)\s*[=:]\s*', stripped)
        if match:
            key = match.group(1)
            seen_keys.setdefault(key, []).append(i)

    for key, line_numbers in seen_keys.items():
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

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
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
    sensitive = {".netrc", ".pgpass", ".env", "credentials", "secrets",
                 ".ssh/config"}

    is_sensitive = basename in sensitive or any(
        s in file_path.lower() for s in ("/ssh/", "credentials", "secrets")
    )

    if not is_sensitive:
        return

    try:
        mode = os.stat(file_path).st_mode
        if mode & stat.S_IROTH or mode & stat.S_IWOTH:
            fa.issues.append(Issue(
                severity=IssueSeverity.WARNING,
                title="Insecure permissions",
                detail=f"Sensitive file is world-readable/writable "
                       f"(mode {oct(mode)[-3:]})",
                file_path=file_path,
                category="security",
                fix_hint=f"chmod 600 {file_path}",
            ))
    except OSError:
        pass
