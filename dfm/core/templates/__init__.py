"""Pre-made config templates for popular applications."""

from dfm.core.templates.types import Template
from dfm.core.templates.registry import (
    TEMPLATES,
    get_templates,
    get_templates_by_category,
)
from dfm.core.templates.installer import install_template

__all__ = [
    "Template",
    "TEMPLATES",
    "get_templates",
    "get_templates_by_category",
    "install_template",
]
