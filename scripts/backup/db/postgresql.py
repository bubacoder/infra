"""Dedicated/shared PostgreSQL logical dumps and matching-client validation."""

import shutil
import subprocess
from pathlib import Path

from ..common import DB_IDENTIFIER, SERVICE_PART, BackupError, docker_dump, require_paired_files, staged_export, valid_relative_path


def validate_target(target: dict, path: Path) -> None:
    single = {"version", "engine", "container", "database", "user"}
    multiple = {"version", "engine", "container", "user", "all_databases", "paired_root", "paired_files"}
    with_pairs = single | {"paired_root", "paired_files"}
    if set(target) not in (single, with_pairs, multiple) or (set(target) == multiple and target["all_databases"] is not True):
        raise BackupError(f"Invalid PostgreSQL backup definition: {path}")
    for key in ("container", "user") if target.get("all_databases") else ("container", "database", "user"):
        if not isinstance(target[key], str) or not DB_IDENTIFIER.fullmatch(target[key]):
            raise BackupError(f"Invalid {key} in {path}")
    if set(target) in (with_pairs, multiple) and (
        not isinstance(target["paired_root"], str)
        or not SERVICE_PART.fullmatch(target["paired_root"])
        or not isinstance(target["paired_files"], list)
        or not target["paired_files"]
        or any(
            not isinstance(item, str) or not valid_relative_path(f"{target['paired_root']}/{item}", target["paired_root"])
            for item in target["paired_files"]
        )
    ):
        raise BackupError(f"Invalid PostgreSQL paired paths in {path}")


def verify_archive(container: str, archive: Path) -> None:
    docker = shutil.which("docker")
    if docker is None:
        raise BackupError("Docker executable not found")
    with archive.open("rb") as stream:
        try:
            subprocess.run(  # noqa: S603
                [docker, "exec", "--interactive", "--user", "postgres", container, "pg_restore", "--list"],
                stdin=stream,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise BackupError(f"Cannot inspect PostgreSQL archive: {error.stderr.strip()}") from error


def postgresql_databases(container: str, user: str) -> list[str]:
    docker = shutil.which("docker")
    if docker is None:
        raise BackupError("Docker executable not found")
    command = [
        docker,
        "exec",
        "--user",
        "postgres",
        container,
        "psql",
        "-U",
        user,
        "-d",
        "postgres",
        "-Atc",
        "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=120)  # noqa: S603
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise BackupError(f"Cannot enumerate PostgreSQL databases in {container}") from error
    names = result.stdout.splitlines()
    if not names or len(names) != len(set(names)) or any(not DB_IDENTIFIER.fullmatch(name) for name in names):
        raise BackupError(f"Unexpected PostgreSQL database names in {container}")
    return names


def export(service: str, target: dict, volumes: Path, export_root: Path) -> Path:
    with staged_export(service, export_root) as run:
        container, user = target["container"], target["user"]
        prefix = ["docker", "exec", "--user", "postgres", container]
        databases = postgresql_databases(container, user) if target.get("all_databases") else [target["database"]]
        files = []
        for database in databases:
            filename = f"database-{database}.dump" if target.get("all_databases") else "database.dump"
            files.append(docker_dump([*prefix, "pg_dump", "--format=custom", "--no-owner", "-U", user, "-d", database], run.directory / filename))
            verify_archive(container, run.directory / filename)
        files.append(docker_dump([*prefix, "pg_dumpall", "--globals-only", "-U", user, "-l", databases[0]], run.directory / "globals.sql"))
        metadata = {"engine": "postgresql", "container": container, "files": files}
        if target.get("all_databases"):
            metadata["databases"] = databases
        else:
            metadata["database"] = databases[0]
        if "paired_root" in target:
            require_paired_files(volumes, target["paired_root"], target["paired_files"])
            metadata.update({"paired_root": target["paired_root"], "paired_files": target["paired_files"]})
        return run.publish(metadata)


def required_files(manifest: dict, target: dict, latest: Path) -> set[str]:
    if not target.get("all_databases"):
        return {"database.dump", "globals.sql"}
    databases = manifest.get("databases")
    if (
        not isinstance(databases, list)
        or not databases
        or len(databases) != len(set(databases))
        or any(not isinstance(name, str) or not DB_IDENTIFIER.fullmatch(name) for name in databases)
    ):
        raise BackupError(f"Invalid PostgreSQL database list in {latest}")
    return {f"database-{name}.dump" for name in databases} | {"globals.sql"}


def verify_export(manifest: dict, target: dict, latest: Path) -> None:
    for filename in required_files(manifest, target, latest) - {"globals.sql"}:
        verify_archive(target["container"], latest / filename)
