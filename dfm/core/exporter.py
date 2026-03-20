"""Import/export functionality for dotfiles."""

import os
import json
import shutil
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from dataclasses import asdict

from dfm.core.scanner import DotfileEntry


def export_dotfiles(entries: list[DotfileEntry], output_path: str,
                    format: str = "tar.gz") -> str:
    """Export selected dotfiles to an archive.

    Args:
        entries: List of dotfile entries to export.
        output_path: Directory to save the archive.
        format: Archive format ('tar.gz' or 'directory').

    Returns:
        Path to the created archive/directory.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    hostname = os.uname().nodename

    if format == "directory":
        export_dir = os.path.join(output_path, f"dotfiles_{hostname}_{timestamp}")
        os.makedirs(export_dir, exist_ok=True)
        _copy_entries_to_dir(entries, export_dir)
        _write_manifest(entries, export_dir)
        return export_dir

    # tar.gz
    archive_name = f"dotfiles_{hostname}_{timestamp}.tar.gz"
    archive_path = os.path.join(output_path, archive_name)

    with tempfile.TemporaryDirectory() as tmpdir:
        staging = os.path.join(tmpdir, "dotfiles")
        os.makedirs(staging)
        _copy_entries_to_dir(entries, staging)
        _write_manifest(entries, staging)

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(staging, arcname="dotfiles")

    return archive_path


def import_dotfiles(archive_path: str, target_home: str | None = None,
                    dry_run: bool = False) -> list[dict]:
    """Import dotfiles from an archive.

    Args:
        archive_path: Path to the archive or directory.
        target_home: Home directory to install to (default: user's home).
        dry_run: If True, only return what would be done.

    Returns:
        List of dicts describing actions taken/planned.
    """
    if target_home is None:
        target_home = str(Path.home())

    actions = []

    if os.path.isdir(archive_path):
        source_dir = archive_path
        manifest = _read_manifest(source_dir)
        actions = _plan_import(source_dir, manifest, target_home)
        if not dry_run:
            _execute_import(actions)
    elif tarfile.is_tarfile(archive_path):
        with tempfile.TemporaryDirectory() as tmpdir:
            with tarfile.open(archive_path, "r:*") as tar:
                tar.extractall(tmpdir, filter="data")

            # Find the dotfiles directory inside
            source_dir = os.path.join(tmpdir, "dotfiles")
            if not os.path.isdir(source_dir):
                # Try first directory found
                for item in os.listdir(tmpdir):
                    candidate = os.path.join(tmpdir, item)
                    if os.path.isdir(candidate):
                        source_dir = candidate
                        break

            manifest = _read_manifest(source_dir)
            actions = _plan_import(source_dir, manifest, target_home)
            if not dry_run:
                _execute_import(actions)

    return actions


def _copy_entries_to_dir(entries: list[DotfileEntry], dest_dir: str) -> None:
    """Copy dotfile entries to a directory, preserving structure."""
    home = str(Path.home())

    for entry in entries:
        if not entry.enabled:
            continue

        # Compute relative path from home
        rel_path = os.path.relpath(entry.path, home)
        dest_path = os.path.join(dest_dir, rel_path)

        if entry.is_directory:
            if os.path.isdir(entry.path):
                shutil.copytree(entry.path, dest_path, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            if os.path.isfile(entry.path):
                shutil.copy2(entry.path, dest_path)


def _write_manifest(entries: list[DotfileEntry], dest_dir: str) -> None:
    """Write a manifest file describing the exported dotfiles."""
    manifest = {
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "hostname": os.uname().nodename,
        "entries": [
            {
                "name": e.name,
                "display_name": e.display_name,
                "path": os.path.relpath(e.path, str(Path.home())),
                "is_directory": e.is_directory,
                "enabled": e.enabled,
            }
            for e in entries if e.enabled
        ],
    }

    manifest_path = os.path.join(dest_dir, "dfm_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)


def _read_manifest(source_dir: str) -> dict | None:
    """Read manifest from an exported directory."""
    manifest_path = os.path.join(source_dir, "dfm_manifest.json")
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _plan_import(source_dir: str, manifest: dict | None,
                 target_home: str) -> list[dict]:
    """Plan import actions."""
    actions = []

    if manifest and "entries" in manifest:
        for entry in manifest["entries"]:
            rel_path = entry["path"]
            source_path = os.path.join(source_dir, rel_path)
            target_path = os.path.join(target_home, rel_path)

            # Guard against path traversal attacks
            if not os.path.realpath(target_path).startswith(
                os.path.realpath(target_home) + os.sep
            ):
                continue

            if not os.path.exists(source_path):
                continue

            action = {
                "name": entry.get("display_name", entry["name"]),
                "source": source_path,
                "target": target_path,
                "is_directory": entry.get("is_directory", False),
                "exists": os.path.exists(target_path),
                "status": "pending",
            }
            actions.append(action)
    else:
        # No manifest: import all files preserving structure
        for root, dirs, files in os.walk(source_dir):
            for fname in files:
                if fname == "dfm_manifest.json":
                    continue
                source_path = os.path.join(root, fname)
                rel_path = os.path.relpath(source_path, source_dir)
                target_path = os.path.join(target_home, rel_path)

                actions.append({
                    "name": rel_path,
                    "source": source_path,
                    "target": target_path,
                    "is_directory": False,
                    "exists": os.path.exists(target_path),
                    "status": "pending",
                })

    return actions


def _execute_import(actions: list[dict]) -> None:
    """Execute planned import actions."""
    for action in actions:
        source = action["source"]
        target = action["target"]

        # Backup existing file
        if action["exists"]:
            backup = target + ".dfm_backup"
            if os.path.isdir(target):
                if os.path.exists(backup):
                    shutil.rmtree(backup)
                shutil.copytree(target, backup)
            else:
                shutil.copy2(target, backup)

        # Copy new file
        try:
            if action.get("is_directory") and os.path.isdir(source):
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(source, target)
            action["status"] = "done"
        except (PermissionError, OSError) as e:
            action["status"] = f"error: {e}"
