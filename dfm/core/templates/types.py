"""Template dataclass."""

from dataclasses import dataclass


@dataclass
class Template:
    """A configuration template."""
    name: str
    app_name: str
    description: str
    category: str
    config_path: str  # Where it should be installed
    content: str
