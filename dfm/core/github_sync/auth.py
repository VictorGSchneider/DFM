"""GitHub CLI availability and authentication helpers."""

import shutil
import subprocess


def is_gh_available() -> bool:
    """Check if GitHub CLI is installed."""
    return shutil.which("gh") is not None


def is_gh_authenticated() -> bool:
    """Check if the user is authenticated with gh."""
    if not is_gh_available():
        return False
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_gh_username() -> str:
    """Get the authenticated GitHub username."""
    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ""


def run_git(args: list[str], cwd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a git command in the given directory."""
    return subprocess.run(
        ["git"] + args,
        cwd=cwd, capture_output=True, text=True, timeout=timeout,
    )
