"""Private export staging, atomic publication and host/Docker primitives."""

import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE_PART = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
DB_IDENTIFIER = re.compile(r"[a-zA-Z_][a-zA-Z0-9_-]*\Z")
DEFAULT_KOPIA_SOURCE = "/sources/local/db-backups"
DEFAULT_KOPIA_VOLUMES_SOURCE = "/sources/local/docker-volumes"


class BackupError(RuntimeError):
    """Invalid configuration or incomplete export."""


def valid_relative_path(value: str, first: str) -> bool:
    """Keep configured source and paired paths inside their service root."""
    path = Path(value)
    return not path.is_absolute() and len(path.parts) >= 2 and path.parts[0] == first and all(part not in {".", ".."} for part in path.parts)


def require_paired_files(volumes: Path, root: str, files: list[str]) -> None:
    if any(not (volumes / root / relative).exists() for relative in files):
        raise BackupError("Required application files are missing from the paired-file inventory")


def private_directory(path: Path) -> None:
    """Refuse existing shared, foreign-owned or symlinked directories."""
    with contextlib.suppress(FileExistsError):
        path.mkdir(mode=0o700)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise BackupError(f"Backup directory must be owned by this user and mode 0700: {path}")


def artifact(path: Path, name: str | None = None) -> dict:
    """Describe a completed artifact without logging its contents."""
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"file": name or path.name, "bytes": path.stat().st_size, "sha256": digest}


@dataclass
class ExportRun:
    """A private staging directory that can be published exactly once."""

    service: str
    directory: Path
    service_directory: Path

    def publish(self, metadata: dict) -> Path:
        now = datetime.now(UTC)
        manifest = {"service": self.service, **metadata, "created_at": now.isoformat()}
        path = self.directory / "manifest.json"
        with path.open("x") as stream:
            path.chmod(0o600)
            json.dump(manifest, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        destination = self.service_directory / now.strftime("%Y%m%dT%H%M%S%fZ")
        self.directory.rename(destination)
        return destination


@contextlib.contextmanager
def staged_export(service: str, export_root: Path) -> Iterator[ExportRun]:
    """Lock one target, clean only its stale staging and remove failed exports."""
    root = export_root
    private_directory(root)
    service_dir = root / service.replace("/", "-")
    private_directory(service_dir)
    with (service_dir / ".lock").open("a+b") as lock:
        (service_dir / ".lock").chmod(0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for stale in service_dir.glob(".incomplete-*"):
            info = stale.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise BackupError(f"Unexpected incomplete export path: {stale}")
            shutil.rmtree(stale)
        temporary = Path(tempfile.mkdtemp(prefix=".incomplete-", dir=service_dir))
        try:
            yield ExportRun(service, temporary, service_dir)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)


def docker_dump(command: list[str], destination: Path) -> dict:
    """Stream a dump into a private host file, checking completion and signature."""
    docker = shutil.which("docker")
    if docker is None:
        raise BackupError("Docker executable not found")
    with destination.open("xb") as stream:
        destination.chmod(0o600)
        try:
            subprocess.run([docker, *command[1:]], stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.PIPE, text=True, check=True)  # noqa: S603
        except subprocess.CalledProcessError as error:
            raise BackupError(f"Export command failed ({error.returncode}): {error.stderr.strip()}") from error
        stream.flush()
        os.fsync(stream.fileno())
    if destination.stat().st_size == 0:
        raise BackupError(f"Empty export: {destination.name}")
    with destination.open("rb") as stream:
        if destination.suffix == ".dump" and stream.read(5) != b"PGDMP":
            raise BackupError(f"Invalid PostgreSQL dump: {destination.name}")
    return artifact(destination)


def container_environment(container: str, name: str) -> str:
    """Read container-held credentials without putting values in args or logs."""
    docker = shutil.which("docker")
    if docker is None:
        raise BackupError("Docker executable not found")
    try:
        result = subprocess.run([docker, "exec", container, "printenv", name], capture_output=True, text=True, check=True, timeout=30)  # noqa: S603
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise BackupError(f"Container {container} is missing {name}") from error
    value = result.stdout.rstrip("\n")
    if not value:
        raise BackupError(f"Container {container} is missing {name}")
    return value


def docker_is_running(container: str) -> bool:
    docker = shutil.which("docker")
    if docker is None:
        raise BackupError("Docker executable not found")
    try:
        result = subprocess.run(  # noqa: S603
            [docker, "inspect", "--format", "{{.State.Running}}", container], capture_output=True, text=True, check=True, timeout=30
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise BackupError(f"Cannot inspect MongoDB writer {container}") from error
    return result.stdout.strip() == "true"
