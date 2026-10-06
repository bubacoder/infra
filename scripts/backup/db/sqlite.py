"""SQLite online snapshots, additional databases and standalone validation."""

import contextlib
import sqlite3
from collections.abc import Callable
from pathlib import Path

from ..common import SERVICE_PART, BackupError, artifact, require_paired_files, staged_export, valid_relative_path


def validate_target(service: str, target: dict, path: Path) -> None:
    name = service.rsplit("/", maxsplit=1)[-1]
    database = target.get("database")
    storage_root = target.get("storage_root", name)
    if (
        not isinstance(storage_root, str)
        or not SERVICE_PART.fullmatch(storage_root)
        or (storage_root != name and not storage_root.startswith(name + "-"))
    ):
        raise BackupError(f"Invalid SQLite storage root in {path}")
    allowed = {"version", "engine", "database"}
    with_pairs = allowed | {"paired_root", "paired_files"}
    with_additional = with_pairs | {"additional_databases"}
    if (
        set(target) - {"storage_root"} not in (allowed, with_pairs, with_additional)
        or not isinstance(database, str)
        or not valid_relative_path(database, storage_root)
        or Path(database).suffix not in {".db", ".sqlite3"}
    ):
        raise BackupError(f"Invalid SQLite backup definition: {path}")
    if "paired_root" in target and (
        target["paired_root"] != storage_root
        or not isinstance(target["paired_files"], list)
        or not target["paired_files"]
        or any(not isinstance(item, str) or not valid_relative_path(f"{storage_root}/{item}", storage_root) for item in target["paired_files"])
    ):
        raise BackupError(f"Invalid paired file paths in {path}")
    if "additional_databases" in target:
        extras = target["additional_databases"]
        if not isinstance(extras, list) or not extras:
            raise BackupError(f"Invalid additional SQLite databases in {path}")
        names = set()
        for extra in extras:
            if (
                not isinstance(extra, dict)
                or set(extra) != {"name", "database"}
                or not isinstance(extra["name"], str)
                or not SERVICE_PART.fullmatch(extra["name"])
                or extra["name"] in names
                or not isinstance(extra["database"], str)
                or not valid_relative_path(extra["database"], storage_root)
                or Path(extra["database"]).suffix not in {".db", ".sqlite3"}
                or extra["database"] == database
            ):
                raise BackupError(f"Invalid additional SQLite databases in {path}")
            names.add(extra["name"])


def verify_sqlite(archive: Path) -> None:
    try:
        with contextlib.closing(sqlite3.connect(f"{archive.as_uri()}?mode=ro", uri=True, timeout=30)) as connection:
            if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise BackupError("SQLite backup failed quick_check")
            if connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0] == 0:
                raise BackupError("SQLite backup has no tables")
    except sqlite3.Error as error:
        raise BackupError("Cannot verify SQLite backup") from error


def sqlite_dump(source: Path, destination: Path) -> dict:
    if not source.is_file() or source.is_symlink():
        raise BackupError(f"SQLite database is missing or symlinked: {source}")
    with destination.open("xb"):
        destination.chmod(0o600)
    try:
        with (
            contextlib.closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True, timeout=30)) as live,
            contextlib.closing(sqlite3.connect(destination, timeout=30)) as backup,
        ):
            live.backup(backup, pages=1000, sleep=0.2)
            if backup.execute("PRAGMA journal_mode=DELETE").fetchone() != ("delete",):
                raise BackupError("Cannot convert SQLite backup to a standalone database")
    except sqlite3.Error as error:
        raise BackupError("SQLite online backup failed") from error
    if any(destination.with_name(destination.name + suffix).exists() for suffix in ("-wal", "-shm")):
        raise BackupError("SQLite backup has unexpected WAL sidecar files")
    verify_sqlite(destination)
    return artifact(destination)


def export(service: str, target: dict, volumes: Path, export_root: Path, *, prepare: Callable[[Path], dict] | None = None) -> Path:
    """Publish generic SQLite state; optional preparation belongs to the owning app."""
    with staged_export(service, export_root) as run:
        sources = [(target["database"], "database.sqlite3")]
        sources.extend((extra["database"], f"database-{extra['name']}.sqlite3") for extra in target.get("additional_databases", []))
        files = []
        extra_metadata = {}
        for index, (relative, filename) in enumerate(sources):
            source = volumes / relative
            if source.parent.is_symlink() or source.is_symlink():
                raise BackupError(f"SQLite source cannot be a symlink: {source}")
            files.append(sqlite_dump(source, run.directory / filename))
            if index == 0 and prepare is not None:
                extra_metadata = prepare(run.directory / filename)
        paired_root = target.get("paired_root", str(Path(target["database"]).parent))
        paired_files = target.get("paired_files", [])
        require_paired_files(volumes, paired_root, paired_files)
        metadata = {
            "engine": "sqlite",
            "database": target["database"],
            "paired_root": paired_root,
            "files": files,
            "paired_files": paired_files,
            **extra_metadata,
        }
        if "additional_databases" in target:
            metadata["additional_databases"] = target["additional_databases"]
        return run.publish(metadata)


def required_files(_manifest: dict, target: dict, _latest: Path) -> set[str]:
    return {"database.sqlite3"} | {f"database-{extra['name']}.sqlite3" for extra in target.get("additional_databases", [])}


def verify_export(manifest: dict, target: dict, latest: Path) -> None:
    for filename in required_files(manifest, target, latest):
        verify_sqlite(latest / filename)
