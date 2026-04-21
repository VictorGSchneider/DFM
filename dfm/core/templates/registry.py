"""Registry of all available templates, grouped by category module."""

from dfm.core.templates.types import Template
from dfm.core.templates.window_managers import WINDOW_MANAGERS
from dfm.core.templates.terminals import TERMINALS
from dfm.core.templates.status_bars import STATUS_BARS
from dfm.core.templates.system import SYSTEM
from dfm.core.templates.shells import SHELLS


TEMPLATES: list[Template] = [
    *WINDOW_MANAGERS,
    *TERMINALS,
    *STATUS_BARS,
    *SYSTEM,
    *SHELLS,
]


def get_templates() -> list[Template]:
    """Get all available templates."""
    return TEMPLATES


def get_templates_by_category() -> dict[str, list[Template]]:
    """Get templates grouped by category."""
    groups: dict[str, list[Template]] = {}
    for t in TEMPLATES:
        groups.setdefault(t.category, []).append(t)
    return groups
