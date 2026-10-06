"""Separate B2 export/application coverage and independently gated local retention."""

import fcntl
import json
import os
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .apps import open_webui
from .common import DEFAULT_KOPIA_SOURCE, DEFAULT_KOPIA_VOLUMES_SOURCE, BackupError, private_directory
from .runner import completed_exports


@dataclass(frozen=True)
class SnapshotSources:
    exports: str = DEFAULT_KOPIA_SOURCE
    applications: str = DEFAULT_KOPIA_VOLUMES_SOURCE


def kopia_has_export(
    service: str,
    export: Path,
    source: str = DEFAULT_KOPIA_SOURCE,
    paired_source: str = DEFAULT_KOPIA_VOLUMES_SOURCE,
    *,
    recent_since: datetime | None = None,
) -> bool:
    docker = shutil.which("docker")
    if docker is None:
        raise BackupError("Docker executable not found")
    if source == paired_source or any(not path.startswith("/sources/") or ".." in Path(path).parts for path in (source, paired_source)):
        raise BackupError("Invalid Kopia source path")
    prefix = [docker, "exec", "kopia-b2", "kopia", "--config-file=/app/config/repository.config"]
    manifest = json.loads((export / "manifest.json").read_text())
    created_at = datetime.fromisoformat(manifest["created_at"])
    not_before = max(created_at, recent_since) if recent_since is not None else created_at
    expected = {entry["file"] for entry in manifest["files"]} | {"manifest.json"}
    export_snapshot = snapshot_cover(prefix, source, f"{service.replace('/', '-')}/{export.name}", expected, not_before)
    if export_snapshot is None:
        return False
    paired_snapshot = None
    if manifest.get("paired_files"):
        paired_root = manifest.get("paired_root") or str(Path(manifest["database"]).parent)
        paired_snapshot = snapshot_cover(prefix, paired_source, paired_root, manifest["paired_files"], not_before)
        if paired_snapshot is None:
            return False
    print(f"{service}: export snapshot {export_snapshot['id']} at {export_snapshot['endTime']}")
    if paired_snapshot:
        print(f"{service}: application snapshot {paired_snapshot['id']} at {paired_snapshot['endTime']}")
    return True


def snapshot_cover(command: list[str], source: str, relative_root: str, paths: set[str] | list[str], not_before: datetime) -> dict | None:
    """Require every path in one complete snapshot started after export publication."""
    if Path(relative_root).is_absolute() or ".." in Path(relative_root).parts:
        raise BackupError("Invalid paired or export root in backup manifest")
    try:
        result = subprocess.run([*command, "snapshot", "list", "--json", source], capture_output=True, text=True, check=True, timeout=120)  # noqa: S603
        snapshots = json.loads(result.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as error:
        raise BackupError("Cannot check Kopia B2 snapshots; refusing local retention") from error
    if not isinstance(snapshots, list):
        raise BackupError("Unexpected Kopia snapshot listing; refusing local retention")
    for snapshot in sorted(snapshots, key=lambda item: item.get("endTime", ""), reverse=True):
        if snapshot.get("source", {}).get("path") != source or snapshot.get("stats", {}).get("errorCount") != 0 or snapshot.get("incompleteReason"):
            continue
        try:
            started_at = datetime.fromisoformat(snapshot["startTime"])
            snapshot_time = datetime.fromisoformat(snapshot["endTime"])
        except (KeyError, ValueError):
            continue
        if started_at < not_before or snapshot_time < started_at:
            continue
        root_id = snapshot.get("rootEntry", {}).get("obj", "")
        if not re.fullmatch(r"k[a-f0-9]+", root_id):
            continue
        if kopia_has_paths(command, f"{root_id}/{relative_root}", paths):
            return {"id": snapshot.get("id", root_id), "endTime": snapshot["endTime"]}
    return None


def kopia_has_paths(command: list[str], root: str, paths: set[str] | list[str]) -> bool:
    grouped = {}
    for relative in paths:
        entry = Path(relative)
        if entry.is_absolute() or ".." in entry.parts:
            raise BackupError("Invalid path in backup manifest")
        grouped.setdefault(entry.parent, set()).add(entry.name)
    for parent, names in grouped.items():
        directory = root if parent == Path(".") else f"{root}/{parent}"
        try:
            listing = subprocess.run([*command, "list", directory], capture_output=True, text=True, check=True, timeout=120)  # noqa: S603
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False
        if not names.issubset(set(listing.stdout.splitlines())):
            return False
    return True


def prune_local(
    service: str,
    volumes: Path,
    export_root: Path,
    keep: int,
    *,
    sources: SnapshotSources | None = None,
) -> list[Path]:
    sources = sources or SnapshotSources()
    if keep < 1:
        raise BackupError("Local retention must keep at least one export")
    root = export_root
    if not root.exists():
        raise BackupError("No database backup root exists for B2 verification")
    private_directory(root)
    service_dir = root / service.replace("/", "-")
    if not service_dir.exists():
        raise BackupError(f"No completed exports for {service}")
    private_directory(service_dir)
    with (service_dir / ".lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        exports = completed_exports(service_dir)
        if not exports:
            raise BackupError(f"No completed exports for {service}")
        if not kopia_has_export(service, exports[-1], sources.exports, sources.applications, recent_since=datetime.now(UTC) - timedelta(days=1)):
            raise BackupError(
                f"No recent Kopia B2 snapshot coverage for the newest {service} export and required paired files; refusing local retention"
            )
        if service == "ai/open-webui":
            open_webui.prune_for_exports(volumes, exports)
        if len(exports) <= keep:
            return []
        for old in exports[:-keep]:
            info = old.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise BackupError(f"Unexpected export directory: {old}")
        removed = exports[:-keep]
        for old in removed:
            shutil.rmtree(old)
        return removed
