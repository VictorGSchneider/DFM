"""Gist upload/download helpers."""

import json
import os
import subprocess

from dfm.core.github_sync.types import SyncStatus
from dfm.core.github_sync.auth import is_gh_authenticated


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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return SyncStatus(
                success=True,
                message=f"Gist created for {basename}",
                url=result.stdout.strip(),
            )
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
    """Download a gist and save to target path."""
    if not is_gh_authenticated():
        return SyncStatus(
            success=False,
            message="Not authenticated. Run 'gh auth login' first.",
        )

    try:
        result = subprocess.run(
            ["gh", "gist", "view", gist_id, "--json", "files,description"],
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

        filename = files[0].get("filename", "config")

        raw_result = subprocess.run(
            ["gh", "gist", "view", gist_id, "--raw"],
            capture_output=True, text=True, timeout=15,
        )
        if raw_result.returncode != 0:
            return SyncStatus(
                success=False,
                message=f"Failed to download gist content: {raw_result.stderr.strip()}",
            )

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
