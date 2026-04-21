"""Types shared by github_sync submodules."""

from dataclasses import dataclass


@dataclass
class SyncStatus:
    """Result of a sync operation."""
    success: bool
    message: str
    url: str = ""
    details: list[str] | None = None
