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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                                errors="replace")
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
    """List the user's gists (`gh gist list` has no JSON output, so use the API)."""
    try:
        result = subprocess.run(
            ["gh", "api", "gists?per_page=30"],
            capture_output=True, text=True, timeout=15, errors="replace",
        )
        if result.returncode == 0:
            return [
                {
                    "id": g.get("id", ""),
                    "description": g.get("description") or "",
                    "files": list((g.get("files") or {}).keys()),
                    "updatedAt": g.get("updated_at", ""),
                    "public": bool(g.get("public")),
                }
                for g in json.loads(result.stdout)
            ]
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError,
            TypeError, AttributeError):
        pass
    return []


def import_gist(gist_id: str, target_path: str,
                filename: str | None = None) -> SyncStatus:
    """Download one file of a gist (the first, unless `filename`) to target path."""
    if not is_gh_authenticated():
        return SyncStatus(
            success=False,
            message="Not authenticated. Run 'gh auth login' first.",
        )

    try:
        if filename is None:
            listing = subprocess.run(
                ["gh", "gist", "view", gist_id, "--files"],
                capture_output=True, text=True, timeout=15, errors="replace",
            )
            if listing.returncode != 0:
                return SyncStatus(
                    success=False,
                    message=f"Failed to fetch gist: {listing.stderr.strip()}",
                )
            names = [n for n in listing.stdout.splitlines() if n.strip()]
            if not names:
                return SyncStatus(success=False, message="Gist has no files")
            filename = names[0]

        # Bytes, not text: keep the file exactly as it was uploaded
        raw_result = subprocess.run(
            ["gh", "gist", "view", gist_id, "--filename", filename, "--raw"],
            capture_output=True, timeout=15,
        )
        if raw_result.returncode != 0:
            err = raw_result.stderr.decode(errors="replace").strip()
            return SyncStatus(
                success=False,
                message=f"Failed to download gist content: {err}",
            )

        # A folder (or "dir/") means "save the gist file in there, under its own name"
        target_path = os.path.expanduser(target_path)
        if target_path.endswith(os.sep) or os.path.isdir(target_path):
            target_path = os.path.join(target_path, os.path.basename(filename))

        if os.path.isfile(target_path):
            from dfm.core.backup import create_backup
            create_backup(target_path, reason="gist-import")

        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(raw_result.stdout)

        return SyncStatus(
            success=True,
            message=f"Imported {filename} from gist to {target_path}",
        )

    except subprocess.TimeoutExpired:
        return SyncStatus(success=False, message="Timed out fetching gist.")
    except OSError as e:
        return SyncStatus(success=False, message=f"Failed to save {target_path}: {e}")
