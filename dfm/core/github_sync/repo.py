"""Dotfiles repo operations: init/clone/push/pull/status/history."""

import os
import shutil
import subprocess
from pathlib import Path

from dfm.core.scanner import DotfileEntry
from dfm.core.github_sync.types import SyncStatus
from dfm.core.github_sync.auth import (
    is_gh_available, is_gh_authenticated, get_gh_username, run_git,
)
from dfm.core.github_sync.repo_config import get_repo_path, save_repo_path


def init_repo(repo_name: str = "dotfiles", private: bool = True) -> SyncStatus:
    """Create a new GitHub repo and initialize local clone."""
    if not is_gh_authenticated():
        return SyncStatus(
            success=False,
            message="Not authenticated. Run 'gh auth login' first.",
        )

    local_path = os.path.join(str(Path.home()), ".dotfiles")
    visibility = "--private" if private else "--public"

    try:
        result = subprocess.run(
            ["gh", "repo", "create", repo_name, visibility,
             "--description", "My dotfiles managed by DFM", "--clone"],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path.home()),
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "already exists" in stderr.lower() or "name already exists" in stderr.lower():
                return clone_repo(repo_name)
            return SyncStatus(success=False,
                              message=f"Failed to create repo: {stderr}")

        cloned_path = os.path.join(str(Path.home()), repo_name)
        if os.path.isdir(cloned_path):
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
        if os.path.isdir(os.path.join(local_path, ".git")):
            save_repo_path(local_path)
            return SyncStatus(
                success=True,
                message=f"Repository already exists at {local_path}",
                url=f"https://github.com/{username}/{repo_name}",
            )
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
    details = _copy_entries_to_repo(entries, home, repo_path)

    if not commit_message:
        commit_message = f"Update dotfiles via DFM ({os.uname().nodename})"

    try:
        run_git(["add", "-A"], cwd=repo_path)

        status = run_git(["status", "--porcelain"], cwd=repo_path)
        if not status.stdout.strip():
            return SyncStatus(
                success=True,
                message="No changes to push - dotfiles are up to date.",
                details=details,
            )

        run_git(["commit", "-m", commit_message], cwd=repo_path)

        push_result = run_git(["push", "-u", "origin", "HEAD"], cwd=repo_path,
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


def _copy_entries_to_repo(entries: list[DotfileEntry], home: str,
                          repo_path: str) -> list[str]:
    details: list[str] = []
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
    return details


def pull_dotfiles() -> SyncStatus:
    """Pull latest dotfiles from GitHub and copy to home."""
    repo_path = get_repo_path()
    if not repo_path or not os.path.isdir(repo_path):
        return SyncStatus(
            success=False,
            message="No repo configured. Initialize or clone a repo first.",
        )

    try:
        pull_result = run_git(["pull", "origin", "HEAD"], cwd=repo_path, timeout=60)
        if pull_result.returncode != 0:
            return SyncStatus(
                success=False,
                message=f"Pull failed: {pull_result.stderr.strip()}",
            )
    except subprocess.TimeoutExpired:
        return SyncStatus(success=False, message="Git pull timed out.")

    details = _copy_repo_to_home(repo_path, str(Path.home()))

    return SyncStatus(
        success=True,
        message=f"Pulled {len([d for d in details if d.startswith('<')])} "
                f"dotfiles from GitHub.",
        details=details,
    )


def _copy_repo_to_home(repo_path: str, home: str) -> list[str]:
    details: list[str] = []
    skip_files = {"dfm_manifest.json", "README.md", "LICENSE", ".gitignore"}
    for root, dirs, files in os.walk(repo_path):
        if ".git" in root.split(os.sep):
            continue
        dirs[:] = [d for d in dirs if d != ".git"]

        for fname in files:
            if fname in skip_files:
                continue

            src = os.path.join(root, fname)
            rel = os.path.relpath(src, repo_path)
            dest = os.path.join(home, rel)

            try:
                if os.path.exists(dest):
                    from dfm.core.backup import create_backup
                    create_backup(dest, reason="pull")

                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(src, dest)
                details.append(f"< {rel}")
            except (PermissionError, OSError) as e:
                details.append(f"! {rel}: {e}")
    return details


def get_commit_history(limit: int = 20) -> list[dict]:
    """Get commit history from the dotfiles repo."""
    repo_path = get_repo_path()
    if not repo_path or not os.path.isdir(repo_path):
        return []

    try:
        result = run_git(
            ["log", f"-{limit}", "--format=%H|%h|%s|%an|%cr|%ci"],
            cwd=repo_path, timeout=10,
        )
        if result.returncode != 0:
            return []

        commits = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("|", 5)
            if len(parts) >= 5:
                files_result = run_git(
                    ["diff-tree", "--no-commit-id", "--name-only", "-r", parts[0]],
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
        r = run_git(["remote", "get-url", "origin"], cwd=repo_path)
        if r.returncode == 0:
            info["remote_url"] = r.stdout.strip()

        r = run_git(["branch", "--show-current"], cwd=repo_path)
        if r.returncode == 0:
            info["branch"] = r.stdout.strip()

        r = run_git(["status", "--porcelain"], cwd=repo_path)
        info["clean"] = not bool(r.stdout.strip())

        r = run_git(["log", "-1", "--format=%h %s (%cr)"], cwd=repo_path)
        if r.returncode == 0:
            info["last_commit"] = r.stdout.strip()

    except subprocess.TimeoutExpired:
        pass

    return info
