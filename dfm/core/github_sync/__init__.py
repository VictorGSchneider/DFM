"""GitHub sync for dotfiles - repo-based sync + gist for single files.

Strategy:
- **Repo sync** (primary): Uses a dedicated `dotfiles` git repo on GitHub.
  This is the community-standard approach. Supports full directory structure,
  commit history, and bidirectional sync (push/pull).
- **Gist** (quick share): Upload a single dotfile as a GitHub Gist for easy
  sharing. Good for sharing one config with someone.

Authentication: Uses `gh` CLI (GitHub CLI) which handles auth via
`gh auth login`. This avoids storing tokens ourselves and leverages
the user's existing GitHub setup.
"""

from dfm.core.github_sync.types import SyncStatus
from dfm.core.github_sync.auth import (
    is_gh_available,
    is_gh_authenticated,
    get_gh_username,
)
from dfm.core.github_sync.gist import upload_gist, list_gists, import_gist
from dfm.core.github_sync.repo_config import get_repo_path, save_repo_path
from dfm.core.github_sync.repo import (
    init_repo,
    clone_repo,
    push_dotfiles,
    pull_dotfiles,
    get_repo_status,
    get_commit_history,
)

__all__ = [
    "SyncStatus",
    "is_gh_available",
    "is_gh_authenticated",
    "get_gh_username",
    "upload_gist",
    "list_gists",
    "import_gist",
    "get_repo_path",
    "save_repo_path",
    "init_repo",
    "clone_repo",
    "push_dotfiles",
    "pull_dotfiles",
    "get_repo_status",
    "get_commit_history",
]
