"""Result types shared by the analyzer and its per-format checks."""

from dataclasses import dataclass, field
from enum import Enum, auto

from dfm.core.scanner import DotfileEntry
from dfm.core.validator import ValidationResult
from dfm.core.conflicts import Conflict
from dfm.core.dependencies import Dependency


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
