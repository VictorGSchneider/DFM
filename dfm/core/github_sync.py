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

import os
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass

from dfm.core.scanner import DotfileEntry


@dataclass
class SyncStatus:
    """Result of a sync operation."""
    success: bool
    message: str
    url: str = ""
    details: list[str] | None = None


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


# ── Gist Operations ────────────────────────────────────────────────


def upload_gist(file_path: str, description: str = "",
                public: bool = False) -> SyncStatus:
    """Upload a single file as a GitHub Gist."""
    if not is_gh_authenticated():
        return SyncStatus(
            success=False,
            message="Not authenticated. Run 'gh auth login' first.",
        )

    if not os.path.isfile(file_path):
        return SyncStatus(success=False, message=f"File not found: {file_path}")

    basename = os.path.basename(file_path)
    if not description:
        description = f"Dotfile: {basename} (uploaded via DFM)"

    cmd = ["gh", "gist", "create", file_path, "--desc", description]
    if public:
        cmd.append("--public")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            return SyncStatus(
                success=True,
                message=f"Gist created for {basename}",
                url=url,
            )
        else:
            return SyncStatus(
                success=False,
                message=f"Failed to create gist: {result.stderr.strip()}",
            )
    except subprocess.TimeoutExpired:
        return SyncStatus(success=False, message="Timed out creating gist.")
    except FileNotFoundError:
        return SyncStatus(success=False, message="gh CLI not found.")


def list_gists() -> list[dict]:
    """List the user's gists."""
    try:
        result = subprocess.run(
            ["gh", "gist", "list", "--limit", "30", "--json",
             "id,description,files,updatedAt,public"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return []


def import_gist(gist_id: str, target_path: str) -> SyncStatus:
    """Download a gist and save to target path.

    Args:
        gist_id: The gist ID or URL
        target_path: Where to save the file
    """
    if not is_gh_authenticated():
        return SyncStatus(
            success=False,
            message="Not authenticated. Run 'gh auth login' first.",
        )

    try:
        # Get gist info
        result = subprocess.run(
            ["gh", "gist", "view", gist_id, "--json",
             "files,description"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return SyncStatus(
                success=False,
                message=f"Failed to fetch gist: {result.stderr.strip()}",
            )

        data = json.loads(result.stdout)
        files = data.get("files", [])
        if not files:
            return SyncStatus(success=False, message="Gist has no files")

        # Get the raw content of the first file
        first_file = files[0]
        filename = first_file.get("filename", "config")

        raw_result = subprocess.run(
            ["gh", "gist", "view", gist_id, "--raw"],
            capture_output=True, text=True, timeout=15,
        )
        if raw_result.returncode != 0:
            return SyncStatus(
                success=False,
                message=f"Failed to download gist content: {raw_result.stderr.strip()}",
            )

        # Backup existing file if present
        if os.path.isfile(target_path):
            from dfm.core.backup import create_backup
            create_backup(target_path, reason="gist-import")

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w") as f:
            f.write(raw_result.stdout)

        return SyncStatus(
            success=True,
            message=f"Imported {filename} from gist to {target_path}",
        )

    except subprocess.TimeoutExpired:
        return SyncStatus(success=False, message="Timed out fetching gist.")
    except (json.JSONDecodeError, KeyError) as e:
        return SyncStatus(success=False, message=f"Failed to parse gist: {e}")


def get_commit_history(limit: int = 20) -> list[dict]:
    """Get commit history from the dotfiles repo.

    Returns list of dicts with keys: hash, short_hash, message, author, date, files_changed
    """
    repo_path = get_repo_path()
    if not repo_path or not os.path.isdir(repo_path):
        return []

    try:
        result = _run_git(
            ["log", f"-{limit}", "--format=%H|%h|%s|%an|%cr|%ci"],
            cwd=repo_path, timeout=10,
        )
        if result.returncode != 0:
            return []

        commits = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("|", 5)
            if len(parts) >= 5:
                # Get files changed for this commit
                files_result = _run_git(
                    ["diff-tree", "--no-commit-id", "--name-only", "-r",
                     parts[0]],
                    cwd=repo_path, timeout=5,
                )
                files = (files_result.stdout.strip().splitlines()
                         if files_result.returncode == 0 else [])

                commits.append({
                    "hash": parts[0],
                    "short_hash": parts[1],
                    "message": parts[2],
                    "author": parts[3],
                    "relative_date": parts[4],
                    "date": parts[5] if len(parts) > 5 else "",
                    "files_changed": files,
                })

        return commits
    except subprocess.TimeoutExpired:
        return []


# ── Repo Sync Operations ──────────────────────────────────────────


def _run_git(args: list[str], cwd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a git command in the given directory."""
    return subprocess.run(
        ["git"] + args,
        cwd=cwd, capture_output=True, text=True, timeout=timeout,
    )


def get_repo_path() -> str:
    """Get the local dotfiles repo path."""
    config_dir = os.path.join(str(Path.home()), ".config", "dfm")
    os.makedirs(config_dir, exist_ok=True)

    config_file = os.path.join(config_dir, "config.json")
    if os.path.isfile(config_file):
        try:
            with open(config_file) as f:
                cfg = json.load(f)
            return cfg.get("repo_path", "")
        except (json.JSONDecodeError, PermissionError):
            pass
    return ""


def save_repo_path(path: str) -> None:
    """Save the configured repo path."""
    config_dir = os.path.join(str(Path.home()), ".config", "dfm")
    os.makedirs(config_dir, exist_ok=True)
    config_file = os.path.join(config_dir, "config.json")

    cfg = {}
    if os.path.isfile(config_file):
        try:
            with open(config_file) as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, PermissionError):
            pass

    cfg["repo_path"] = path
    with open(config_file, "w") as f:
        json.dump(cfg, f, indent=2)


def init_repo(repo_name: str = "dotfiles",
              private: bool = True) -> SyncStatus:
    """Create a new GitHub repo and initialize local clone."""
    if not is_gh_authenticated():
        return SyncStatus(
            success=False,
            message="Not authenticated. Run 'gh auth login' first.",
        )

    local_path = os.path.join(str(Path.home()), ".dotfiles")

    # Create GitHub repo
    visibility = "--private" if private else "--public"
    try:
        result = subprocess.run(
            ["gh", "repo", "create", repo_name, visibility,
             "--description", "My dotfiles managed by DFM",
             "--clone"],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path.home()),
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            # If repo already exists, try to clone it
            if "already exists" in stderr.lower() or "name already exists" in stderr.lower():
                return clone_repo(repo_name)
            return SyncStatus(success=False,
                              message=f"Failed to create repo: {stderr}")

        # The repo was cloned into ~/repo_name by gh
        cloned_path = os.path.join(str(Path.home()), repo_name)
        if os.path.isdir(cloned_path):
            # Move to ~/.dotfiles if different
            if cloned_path != local_path and not os.path.exists(local_path):
                shutil.move(cloned_path, local_path)
            elif cloned_path != local_path:
                local_path = cloned_path

        save_repo_path(local_path)

        return SyncStatus(
            success=True,
            message=f"Repository created and cloned to {local_path}",
            url=f"https://github.com/{get_gh_username()}/{repo_name}",
        )
    except subprocess.TimeoutExpired:
        return SyncStatus(success=False, message="Timed out creating repo.")
    except FileNotFoundError:
        return SyncStatus(success=False, message="gh CLI not found.")


def clone_repo(repo_name: str = "dotfiles") -> SyncStatus:
    """Clone an existing dotfiles repo from GitHub."""
    if not is_gh_authenticated():
        return SyncStatus(
            success=False,
            message="Not authenticated. Run 'gh auth login' first.",
        )

    username = get_gh_username()
    local_path = os.path.join(str(Path.home()), ".dotfiles")

    if os.path.isdir(local_path):
        # Already exists, check if it's a git repo
        if os.path.isdir(os.path.join(local_path, ".git")):
            save_repo_path(local_path)
            return SyncStatus(
                success=True,
                message=f"Repository already exists at {local_path}",
                url=f"https://github.com/{username}/{repo_name}",
            )
        else:
            return SyncStatus(
                success=False,
                message=f"{local_path} exists but is not a git repo.",
            )

    try:
        result = subprocess.run(
            ["gh", "repo", "clone", f"{username}/{repo_name}", local_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            save_repo_path(local_path)
            return SyncStatus(
                success=True,
                message=f"Cloned to {local_path}",
                url=f"https://github.com/{username}/{repo_name}",
            )
        else:
            return SyncStatus(
                success=False,
                message=f"Clone failed: {result.stderr.strip()}",
            )
    except subprocess.TimeoutExpired:
        return SyncStatus(success=False, message="Timed out cloning repo.")


def push_dotfiles(entries: list[DotfileEntry],
                  commit_message: str = "") -> SyncStatus:
    """Copy enabled dotfiles into the repo, commit, and push."""
    repo_path = get_repo_path()
    if not repo_path or not os.path.isdir(repo_path):
        return SyncStatus(
            success=False,
            message="No repo configured. Initialize or clone a repo first.",
        )

    home = str(Path.home())
    details = []

    for entry in entries:
        if not entry.enabled:
            continue

        src = entry.path
        rel = os.path.relpath(src, home)
        dest = os.path.join(repo_path, rel)

        try:
            if entry.is_directory and os.path.isdir(src):
                os.makedirs(dest, exist_ok=True)
                shutil.copytree(src, dest, dirs_exist_ok=True)
                details.append(f"+ {rel}/")
            elif os.path.isfile(src):
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(src, dest)
                details.append(f"+ {rel}")
        except (PermissionError, OSError) as e:
            details.append(f"! {rel}: {e}")

    if not commit_message:
        commit_message = f"Update dotfiles via DFM ({os.uname().nodename})"

    # Git add, commit, push
    try:
        _run_git(["add", "-A"], cwd=repo_path)

        # Check if there's anything to commit
        status = _run_git(["status", "--porcelain"], cwd=repo_path)
        if not status.stdout.strip():
            return SyncStatus(
                success=True,
                message="No changes to push - dotfiles are up to date.",
                details=details,
            )

        _run_git(["commit", "-m", commit_message], cwd=repo_path)

        push_result = _run_git(["push", "-u", "origin", "HEAD"], cwd=repo_path,
                               timeout=60)
        if push_result.returncode != 0:
            return SyncStatus(
                success=False,
                message=f"Push failed: {push_result.stderr.strip()}",
                details=details,
            )

        return SyncStatus(
            success=True,
            message=f"Pushed {len([d for d in details if d.startswith('+')])} "
                    f"dotfiles to GitHub.",
            details=details,
        )
    except subprocess.TimeoutExpired:
        return SyncStatus(success=False, message="Git push timed out.")


def pull_dotfiles() -> SyncStatus:
    """Pull latest dotfiles from GitHub and copy to home."""
    repo_path = get_repo_path()
    if not repo_path or not os.path.isdir(repo_path):
        return SyncStatus(
            success=False,
            message="No repo configured. Initialize or clone a repo first.",
        )

    home = str(Path.home())

    # Pull latest
    try:
        pull_result = _run_git(["pull", "origin", "HEAD"], cwd=repo_path,
                               timeout=60)
        if pull_result.returncode != 0:
            return SyncStatus(
                success=False,
                message=f"Pull failed: {pull_result.stderr.strip()}",
            )
    except subprocess.TimeoutExpired:
        return SyncStatus(success=False, message="Git pull timed out.")

    # Copy files from repo to home
    details = []
    for root, dirs, files in os.walk(repo_path):
        # Skip .git directory
        if ".git" in root.split(os.sep):
            continue
        dirs[:] = [d for d in dirs if d != ".git"]

        for fname in files:
            if fname in ("dfm_manifest.json", "README.md", "LICENSE",
                         ".gitignore"):
                continue

            src = os.path.join(root, fname)
            rel = os.path.relpath(src, repo_path)
            dest = os.path.join(home, rel)

            try:
                # Backup existing
                if os.path.exists(dest):
                    backup = dest + ".dfm_backup"
                    shutil.copy2(dest, backup)

                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(src, dest)
                details.append(f"< {rel}")
            except (PermissionError, OSError) as e:
                details.append(f"! {rel}: {e}")

    return SyncStatus(
        success=True,
        message=f"Pulled {len([d for d in details if d.startswith('<')])} "
                f"dotfiles from GitHub.",
        details=details,
    )


def get_repo_status() -> dict:
    """Get the current status of the dotfiles repo."""
    repo_path = get_repo_path()
    info = {
        "configured": bool(repo_path),
        "path": repo_path,
        "exists": False,
        "remote_url": "",
        "branch": "",
        "clean": True,
        "last_commit": "",
        "gh_available": is_gh_available(),
        "gh_authenticated": False,
        "username": "",
    }

    if not repo_path:
        info["gh_authenticated"] = is_gh_authenticated()
        if info["gh_authenticated"]:
            info["username"] = get_gh_username()
        return info

    if not os.path.isdir(os.path.join(repo_path, ".git")):
        return info

    info["exists"] = True
    info["gh_authenticated"] = is_gh_authenticated()
    if info["gh_authenticated"]:
        info["username"] = get_gh_username()

    try:
        # Remote URL
        r = _run_git(["remote", "get-url", "origin"], cwd=repo_path)
        if r.returncode == 0:
            info["remote_url"] = r.stdout.strip()

        # Branch
        r = _run_git(["branch", "--show-current"], cwd=repo_path)
        if r.returncode == 0:
            info["branch"] = r.stdout.strip()

        # Clean?
        r = _run_git(["status", "--porcelain"], cwd=repo_path)
        info["clean"] = not bool(r.stdout.strip())

        # Last commit
        r = _run_git(["log", "-1", "--format=%h %s (%cr)"], cwd=repo_path)
        if r.returncode == 0:
            info["last_commit"] = r.stdout.strip()

    except subprocess.TimeoutExpired:
        pass

    return info
