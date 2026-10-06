"""Full-instance MongoDB archives with standalone-writer quiescing."""

import gzip
import shutil
import signal
import subprocess
import tempfile
import zlib
from pathlib import Path

import yaml

from ..common import (
    DB_IDENTIFIER,
    SERVICE_PART,
    BackupError,
    container_environment,
    docker_dump,
    docker_is_running,
    require_paired_files,
    staged_export,
    valid_relative_path,
)


def validate_target(target: dict, path: Path) -> None:
    expected = {"version", "engine", "container", "writer", "paired_root", "paired_files"}
    if set(target) != expected or any(
        not isinstance(target[key], str) or not SERVICE_PART.fullmatch(target[key]) for key in ("container", "writer", "paired_root")
    ):
        raise BackupError(f"Invalid MongoDB backup definition: {path}")
    if (
        target["paired_root"] != target["writer"]
        or not isinstance(target["paired_files"], list)
        or not target["paired_files"]
        or any(
            not isinstance(item, str) or not valid_relative_path(f"{target['paired_root']}/{item}", target["paired_root"])
            for item in target["paired_files"]
        )
    ):
        raise BackupError(f"Invalid MongoDB paired paths in {path}")


def verify_mongo_archive(archive: Path) -> None:
    try:
        with gzip.open(archive, "rb") as stream:
            for _block in iter(lambda: stream.read(1024 * 1024), b""):
                pass
    except (gzip.BadGzipFile, EOFError, zlib.error) as error:
        raise BackupError("Invalid compressed MongoDB archive") from error


def dump_instance(target: dict, destination: Path) -> dict:
    """Keep credentials in tmpfs and restart a paused writer even on failure."""
    docker = shutil.which("docker")
    if docker is None:
        raise BackupError("Docker executable not found")
    container, writer = target["container"], target["writer"]
    container_config = Path("/dev/shm") / "infra-db-backup-mongo.yaml"  # noqa: S108 - container tmpfs
    username = container_environment(container, "MONGO_INITDB_ROOT_USERNAME")
    password = container_environment(container, "MONGO_INITDB_ROOT_PASSWORD")
    if not DB_IDENTIFIER.fullmatch(username):
        raise BackupError("Invalid MongoDB backup username")
    with tempfile.TemporaryDirectory(prefix="infra-db-backup-mongo-", dir="/dev/shm") as secret_dir:
        secret_file = Path(secret_dir) / "credentials.yaml"
        with secret_file.open("x") as stream:
            secret_file.chmod(0o600)
            yaml.safe_dump({"password": password}, stream)
        subprocess.run([docker, "exec", container, "rm", "-f", str(container_config)], check=True, stdout=subprocess.DEVNULL)  # noqa: S603
        with secret_file.open("rb") as stream:
            subprocess.run(  # noqa: S603
                [docker, "exec", "--interactive", container, "sh", "-c", f"umask 077; cat > {container_config}"],
                stdin=stream,
                check=True,
                stdout=subprocess.DEVNULL,
            )
        try:
            original_handler = signal.getsignal(signal.SIGTERM)

            def stop_requested(_signum: int, _frame: object) -> None:
                raise BackupError("MongoDB export was interrupted")

            signal.signal(signal.SIGTERM, stop_requested)
            was_running = docker_is_running(writer)
            paused = False
            try:
                if was_running:
                    paused = True
                    subprocess.run([docker, "stop", "--time", "30", writer], check=True, stdout=subprocess.DEVNULL)  # noqa: S603
                result = docker_dump(
                    [
                        "docker",
                        "exec",
                        container,
                        "mongodump",
                        f"--config={container_config}",
                        "--username",
                        username,
                        "--authenticationDatabase",
                        "admin",
                        "--archive",
                        "--gzip",
                    ],
                    destination,
                )
                verify_mongo_archive(destination)
            finally:
                try:
                    if paused and not docker_is_running(writer):
                        subprocess.run([docker, "start", writer], check=True, stdout=subprocess.DEVNULL)  # noqa: S603
                finally:
                    signal.signal(signal.SIGTERM, original_handler)
        finally:
            subprocess.run([docker, "exec", container, "rm", "-f", str(container_config)], check=True, stdout=subprocess.DEVNULL)  # noqa: S603
    return result


def export(service: str, target: dict, volumes: Path, export_root: Path) -> Path:
    with staged_export(service, export_root) as run:
        files = [dump_instance(target, run.directory / "database.archive.gz")]
        require_paired_files(volumes, target["paired_root"], target["paired_files"])
        return run.publish(
            {
                "engine": "mongodb",
                "container": target["container"],
                "files": files,
                "paired_root": target["paired_root"],
                "paired_files": target["paired_files"],
            }
        )


def required_files(_manifest: dict, _target: dict, _latest: Path) -> set[str]:
    return {"database.archive.gz"}


def verify_export(_manifest: dict, _target: dict, latest: Path) -> None:
    verify_mongo_archive(latest / "database.archive.gz")
