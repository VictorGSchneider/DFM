"""Dotfiles repo operations: init/clone/push/pull/status/history."""

import filecmp
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
from dfm.core.github_sync.layout import detect_layout, repo_files, repo_rel


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
    if not username:
        return SyncStatus(
            success=False,
            message="Could not determine your GitHub username (gh api user failed).",
        )
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
    targets: list[str] = []
    details = _copy_entries_to_repo(entries, home, repo_path, targets)

    if not commit_message:
        commit_message = f"Update dotfiles via DFM ({os.uname().nodename})"

    if not targets:
        return SyncStatus(success=True,
                          message="No changes to push - dotfiles are up to date.",
                          details=details)

    try:
        # Only touch what DFM copied: an existing repo may hold other work in progress.
        added = run_git(["add", "--"] + targets, cwd=repo_path)
        if added.returncode != 0:
            return SyncStatus(success=False,
                              message=f"git add failed: {added.stderr.strip()}",
                              details=details)

        status = run_git(["status", "--porcelain", "--"] + targets, cwd=repo_path)
        if not status.stdout.strip():
            return SyncStatus(
                success=True,
                message="No changes to push - dotfiles are up to date.",
                details=details,
            )

        committed = run_git(["commit", "-m", commit_message, "--"] + targets,
                            cwd=repo_path)
        if committed.returncode != 0:
            reason = (committed.stderr or committed.stdout).strip()
            return SyncStatus(success=False,
                              message=f"Commit failed: {reason}",
                              details=details)

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
                    f"dotfiles.",
            details=details,
        )
    except subprocess.TimeoutExpired:
        return SyncStatus(success=False, message="Git push timed out.")


def _copy_entries_to_repo(entries: list[DotfileEntry], home: str,
                          repo_path: str,
                          targets: list[str] | None = None) -> list[str]:
    """Copy enabled entries into the repo; `targets` collects the repo paths written."""
    details: list[str] = []
    layout = detect_layout(repo_path)
    for entry in entries:
        if not entry.enabled:
            continue

        src = entry.path
        rel = os.path.relpath(src, home)
        target = repo_rel(repo_path, rel, layout)
        dest = os.path.join(repo_path, target)

        try:
            if entry.is_directory and os.path.isdir(src):
                os.makedirs(dest, exist_ok=True)
                shutil.copytree(src, dest, dirs_exist_ok=True,
                                ignore_dangling_symlinks=True)
                details.append(f"+ {rel}/")
                if targets is not None:
                    targets.append(target)
            elif os.path.isfile(src):
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(src, dest)
                details.append(f"+ {rel}")
                if targets is not None:
                    targets.append(target)
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
        pull_result = run_git(["pull"], cwd=repo_path, timeout=60)
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


def pull_preview(repo_path: str) -> tuple[list[str], list[str]]:
    """What a pull would do: (files that differ from home, files home lacks).

    Paths are relative to the home folder; files identical to the repo's are left out.
    """
    home = str(Path.home())
    overwrite: list[str] = []
    new: list[str] = []
    for repo_rel_path, home_rel in repo_files(repo_path):
        dest = os.path.join(home, home_rel)
        if not os.path.exists(dest):
            new.append(home_rel)
        elif not _same_file(os.path.join(repo_path, repo_rel_path), dest):
            overwrite.append(home_rel)
    return overwrite, new


def _same_file(a: str, b: str) -> bool:
    try:
        return filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


def _copy_repo_to_home(repo_path: str, home: str) -> list[str]:
    details: list[str] = []
    for repo_rel_path, home_rel in repo_files(repo_path):
        src = os.path.join(repo_path, repo_rel_path)
        dest = os.path.join(home, home_rel)
        if os.path.exists(dest) and _same_file(src, dest):
            continue

        try:
            if os.path.exists(dest):
                from dfm.core.backup import create_backup
                create_backup(dest, reason="pull")

            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            details.append(f"< {home_rel}")
        except (PermissionError, OSError) as e:
            details.append(f"! {home_rel}: {e}")
    return details


def get_commit_history(limit: int = 20) -> list[dict]:
    """Get commit history from the dotfiles repo."""
    repo_path = get_repo_path()
    if not repo_path or not os.path.isdir(repo_path):
        return []

    try:
        # ASCII separators: commit subjects and author names may contain any
        # printable character (including "|"). --name-only avoids a git call per commit.
        result = run_git(
            ["log", f"-{limit}", "--name-only",
             "--format=%x1e%H%x1f%h%x1f%s%x1f%an%x1f%cr%x1f%ci"],
            cwd=repo_path, timeout=15,
        )
        if result.returncode != 0:
            return []

        commits = []
        for record in result.stdout.split("\x1e"):
            if not record.strip():
                continue
            header, _, names = record.partition("\n")
            parts = header.split("\x1f")
            if len(parts) < 6:
                continue
            commits.append({
                "hash": parts[0],
                "short_hash": parts[1],
                "message": parts[2],
                "author": parts[3],
                "relative_date": parts[4],
                "date": parts[5],
                "files_changed": [n for n in names.splitlines() if n.strip()],
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
        "layout": "",
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
    info["layout"] = detect_layout(repo_path)
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


def get_remote_url() -> str:
    """The configured repo's `origin` URL, or "" when there is none."""
    repo_path = get_repo_path()
    if not repo_path or not os.path.isdir(os.path.join(repo_path, ".git")):
        return ""
    try:
        r = run_git(["remote", "get-url", "origin"], cwd=repo_path)
    except subprocess.TimeoutExpired:
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


# Where people usually keep a dotfiles clone, most likely first.
_COMMON_LOCATIONS = (".dotfiles", "dotfiles", ".config/dotfiles", "Documents/dotfiles")


def find_existing_repos() -> list[str]:
    """Git clones in the usual places, to offer as a starting point."""
    home = Path.home()
    return [str(home / rel) for rel in _COMMON_LOCATIONS
            if (home / rel / ".git").exists()]


def inspect_repo(path: str) -> SyncStatus:
    """Check that `path` is the root of a git clone DFM can sync with.

    On success `details` holds a summary: remote, branch, layout, file count,
    uncommitted changes. Nothing is changed.
    """
    path = os.path.realpath(os.path.expanduser(path or ""))
    if not os.path.isdir(path):
        return SyncStatus(success=False, message=f"{path} is not a folder.")

    try:
        top = run_git(["rev-parse", "--show-toplevel"], cwd=path)
    except FileNotFoundError:
        return SyncStatus(success=False, message="git was not found.")
    except subprocess.TimeoutExpired:
        return SyncStatus(success=False, message="git did not answer.")
    if top.returncode != 0:
        return SyncStatus(success=False,
                          message=f"{path} is not a git repository.")
    root = os.path.realpath(top.stdout.strip())
    if root != path:
        return SyncStatus(
            success=False,
            message=f"{path} is inside a repository, not its root. "
                    f"Choose {root} instead.")

    try:
        remote = run_git(["remote", "get-url", "origin"], cwd=path)
        branch = run_git(["branch", "--show-current"], cwd=path)
        dirty = run_git(["status", "--porcelain"], cwd=path)
    except subprocess.TimeoutExpired:
        return SyncStatus(success=False, message="git did not answer.")

    layout = detect_layout(path)
    details = [
        "Remote: " + (remote.stdout.strip() if remote.returncode == 0
                      else "none (you can commit, but not push or pull)"),
        "Branch: " + (branch.stdout.strip() or "(detached)"),
        f"Layout: {layout}" + (" (one folder per program)" if layout == "stow"
                               else " (files laid out like your home folder)"),
        f"Dotfiles in it: {len(repo_files(path, layout))}",
    ]
    if dirty.stdout.strip():
        details.append("It has uncommitted changes; DFM will leave them alone.")
    return SyncStatus(success=True, message=path, details=details)


def use_existing_repo(path: str) -> SyncStatus:
    """Make an already-cloned repo the dotfiles repo. Needs no network or `gh`."""
    checked = inspect_repo(path)
    if not checked.success:
        return checked
    save_repo_path(checked.message)
    return SyncStatus(success=True,
                      message=f"Using the existing repository at {checked.message}",
                      details=checked.details)
