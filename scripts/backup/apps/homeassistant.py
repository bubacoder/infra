"""Request and validate Home Assistant Container's supported local backup."""

import contextlib
import gzip
import json
import os
import shutil
import sqlite3
import stat
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..common import ROOT, BackupError, artifact, staged_export, valid_relative_path
from ..db.sqlite import verify_sqlite


class HomeAssistantBackupError(ValueError):
    """The native backup could not be completed or verified."""


def create_backup(data: Path, token_path: Path) -> Path:
    """Call backup.create; select only the newly completed local archive."""
    try:
        info = token_path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise HomeAssistantBackupError("Home Assistant backup-token must be owned by the backup user and mode 0600")
        token = token_path.read_text().strip()
        if not token or any(character.isspace() for character in token):
            raise HomeAssistantBackupError("Home Assistant backup-token is empty or invalid")
    except OSError as error:
        raise HomeAssistantBackupError(f"Save an administrator long-lived token in {token_path} (mode 0600)") from error
    backups = data / "backups"
    before = set(backups.glob("*.tar"))
    request = urllib.request.Request(
        "http://127.0.0.1:8123/api/services/backup/create",
        data=b"{}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:  # noqa: S310 - fixed loopback endpoint
            response.read()
    except urllib.error.URLError as error:
        raise HomeAssistantBackupError("Home Assistant backup.create failed; check token/admin access and the native backup integration") from error
    # REST service calls may return before a long-running job finishes.
    deadline = time.monotonic() + 600
    previous = None
    while time.monotonic() < deadline:
        candidates = set(backups.glob("*.tar")) - before
        if len(candidates) > 1:
            raise HomeAssistantBackupError("Multiple new Home Assistant backups appeared; refusing an ambiguous capture")
        if candidates:
            candidate = candidates.pop()
            if candidate.is_symlink():
                raise HomeAssistantBackupError("Native Home Assistant archive must not be a symlink")
            current = (candidate, candidate.stat().st_size, candidate.stat().st_mtime_ns)
            if current == previous and current[1] > 0:
                return candidate
            previous = current
        time.sleep(2)
    raise HomeAssistantBackupError("Timed out waiting for a completed native Home Assistant backup")


def validate_backup(archive: Path, required: list[str], database_output: Path | None = None) -> dict:
    """Check native metadata, config inventory and recorder DB including its WAL."""
    try:
        with tarfile.open(archive, "r:") as outer:
            members = {member.name.removeprefix("./"): member for member in outer.getmembers()}
            metadata_member = members["backup.json"]
            payload_member = members["homeassistant.tar.gz"]
            if not metadata_member.isfile() or not payload_member.isfile():
                raise HomeAssistantBackupError("Native Home Assistant backup has invalid payload members")
            with outer.extractfile(metadata_member) as stream:
                metadata = json.load(stream)
            if metadata.get("protected") is not False or metadata.get("homeassistant", {}).get("exclude_database") is not False:
                raise HomeAssistantBackupError("Expected an unencrypted native backup with the recorder database included")
            with tempfile.TemporaryDirectory(prefix="ha-backup-verify-") as temporary:
                destination = Path(temporary)
                names = set()
                with outer.extractfile(payload_member) as payload, gzip.GzipFile(fileobj=payload) as compressed:
                    with tarfile.open(fileobj=compressed, mode="r|") as inner:
                        for member in inner:
                            name = member.name.removeprefix("./")
                            if name in required and not member.isfile():
                                raise HomeAssistantBackupError("Required Home Assistant backup entry is not a regular file")
                            if member.isfile():
                                names.add(name)
                                with inner.extractfile(member) as stream:
                                    if name in {"data/home-assistant_v2.db", "data/home-assistant_v2.db-wal"}:
                                        with (destination / Path(name).name).open("xb") as output:
                                            shutil.copyfileobj(stream, output)
                                    else:
                                        for _block in iter(lambda: stream.read(1024 * 1024), b""):
                                            pass
                    # Consume the gzip trailer too, so truncated payloads fail.
                    for _block in iter(lambda: compressed.read(1024 * 1024), b""):
                        pass
                if not set(required).issubset(names):
                    raise HomeAssistantBackupError("Native Home Assistant backup is missing required configuration or database files")
                source = destination / "home-assistant_v2.db"
                with contextlib.closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)) as connection:
                    if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
                        raise HomeAssistantBackupError("Native Home Assistant recorder database failed quick_check")
                    if database_output is not None:
                        with contextlib.closing(sqlite3.connect(database_output)) as backup:
                            connection.backup(backup)
                            backup.execute("PRAGMA journal_mode=DELETE")
                        database_output.chmod(0o600)
                return {
                    "native_backup_id": metadata["slug"],
                    "homeassistant_version": metadata["homeassistant"]["version"],
                    "config_file_count": len(names),
                }
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, tarfile.TarError, EOFError) as error:
        if isinstance(error, HomeAssistantBackupError):
            raise
        raise HomeAssistantBackupError("Cannot validate native Home Assistant backup") from error


def validate_target(service: str, target: dict, path: Path) -> None:
    if (
        set(target) != {"version", "engine", "container", "data", "token_file", "required_files"}
        or service != "automation/homeassistant"
        or target["container"] != "homeassistant"
        or target["data"] != "homeassistant"
        or target["token_file"] != "homeassistant/backup-token"  # noqa: S105 - file path, not a token
        or not isinstance(target["required_files"], list)
        or not {"data/configuration.yaml", "data/.storage/auth", "data/home-assistant_v2.db"}.issubset(target["required_files"])
        or any(not isinstance(item, str) or not valid_relative_path(item, "data") for item in target["required_files"])
    ):
        raise BackupError(f"Invalid Home Assistant backup definition: {path}")


def enabled(host: str, export_root: Path, root: Path = ROOT) -> bool:
    return (root / "config/docker" / host / "homeassistant/backup-token").exists() or (export_root / "automation-homeassistant").exists()


def export(service: str, target: dict, volumes: Path, export_root: Path, host: str = "localhost") -> Path:
    with staged_export(service, export_root) as run:
        try:
            native = create_backup(volumes / target["data"], ROOT / "config/docker" / host / target["token_file"])
            archive = run.directory / "homeassistant.tar"
            shutil.copyfile(native, archive)
            archive.chmod(0o600)
            metadata = validate_backup(archive, target["required_files"], run.directory / "database.sqlite3")
            files = [artifact(path) for path in (archive, run.directory / "database.sqlite3")]
            verify_sqlite(run.directory / "database.sqlite3")
            destination = run.publish({"engine": "homeassistant", "files": files, **metadata})
            # Delete only the newly published duplicate, not pre-existing UI backups.
            native.unlink()
        except HomeAssistantBackupError as error:
            raise BackupError(str(error)) from error
        return destination


def required_files(_manifest: dict, _target: dict, _latest: Path) -> set[str]:
    return {"homeassistant.tar", "database.sqlite3"}


def verify_export(_manifest: dict, target: dict, latest: Path) -> None:
    try:
        validate_backup(latest / "homeassistant.tar", target["required_files"])
    except HomeAssistantBackupError as error:
        raise BackupError(str(error)) from error
    verify_sqlite(latest / "database.sqlite3")
