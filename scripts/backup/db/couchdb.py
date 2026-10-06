"""Supported append-only CouchDB backup, preserving index-before-shard order."""

import base64
import ipaddress
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from ..common import BackupError, artifact, container_environment, staged_export, valid_relative_path


def validate_target(service: str, target: dict, path: Path) -> None:
    name = service.rsplit("/", maxsplit=1)[-1]
    if (
        set(target) != {"version", "engine", "container", "data", "config"}
        or target["container"] != name
        or target["data"] != f"{name}/data"
        or target["config"] != f"{name}/etc"
    ):
        raise BackupError(f"Invalid CouchDB backup definition: {path}")


def couchdb_databases(container: str) -> list[str]:
    docker = shutil.which("docker")
    if docker is None:
        raise BackupError("Docker executable not found")
    try:
        result = subprocess.run(  # noqa: S603
            [docker, "inspect", "--format", "{{json .NetworkSettings.Networks}}", container],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        networks = json.loads(result.stdout)
        network = networks.get("proxy") or next(iter(networks.values()))
        address = str(ipaddress.ip_address(network["IPAddress"]))
        username = container_environment(container, "COUCHDB_USER")
        password = container_environment(container, "COUCHDB_PASSWORD")
        authorization = base64.b64encode(f"{username}:{password}".encode()).decode()
        request = urllib.request.Request(f"http://{address}:5984/_all_dbs", headers={"Authorization": f"Basic {authorization}"})
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - validated Docker bridge IP
            names = json.load(response)
    except (OSError, ValueError, KeyError, StopIteration, urllib.error.URLError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise BackupError("Cannot query CouchDB database inventory") from error
    if not isinstance(names, list) or not {"_users", "_replicator"}.issubset(names) or any(not isinstance(name, str) for name in names):
        raise BackupError("Unexpected CouchDB database inventory")
    return sorted(names)


def couchdb_files(root: Path) -> list[Path]:
    indexes = sorted(path for path in (root / ".shards").rglob("*") if path.is_file()) if (root / ".shards").exists() else []
    shards = sorted(path for path in (root / "shards").rglob("*.couch") if path.is_file())
    system = sorted(path for path in root.glob("*.couch") if path.is_file())
    if not shards or {"_dbs.couch", "_nodes.couch"} - {path.name for path in system}:
        raise BackupError("CouchDB shard or system database files are missing")
    files = [*indexes, *shards, *system]
    if any(path.is_symlink() for path in files):
        raise BackupError("CouchDB database files must not be symlinks")
    return files


def export(service: str, target: dict, volumes: Path, export_root: Path) -> Path:
    with staged_export(service, export_root) as run:
        data_root, config_root = volumes / target["data"], volumes / target["config"]
        before = couchdb_databases(target["container"])
        database_sources = couchdb_files(data_root)
        if not config_root.is_dir():
            raise BackupError("CouchDB runtime config is missing")
        sources = [*database_sources, *sorted(path for path in config_root.rglob("*") if path.is_file())]
        files = []
        for source in sources:
            if source.is_symlink():
                raise BackupError("CouchDB config files must not be symlinks")
            relative = source.relative_to(volumes)
            destination = run.directory / relative
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            destination.chmod(0o600)
            files.append(artifact(destination, str(relative)))
        if before != couchdb_databases(target["container"]) or database_sources != couchdb_files(data_root):
            raise BackupError("CouchDB database inventory changed during export")
        return run.publish({"engine": "couchdb", "container": target["container"], "databases": before, "files": files})


def required_files(manifest: dict, _target: dict, latest: Path) -> set[str]:
    entries = manifest.get("files")
    required = {entry.get("file") for entry in entries if isinstance(entry, dict)} if isinstance(entries, list) else set()
    if (
        not required
        or not {"couchdb/data/_dbs.couch", "couchdb/data/_nodes.couch"}.issubset(required)
        or any(
            not isinstance(name, str) or not valid_relative_path(name, "couchdb") or Path(name).parts[1] not in {"data", "etc"} for name in required
        )
    ):
        raise BackupError(f"Incomplete CouchDB file manifest in {latest}")
    return required


def verify_export(manifest: dict, _target: dict, latest: Path) -> None:
    if not isinstance(manifest.get("databases"), list) or not {"_users", "_replicator"}.issubset(manifest["databases"]):
        raise BackupError(f"Incomplete CouchDB database inventory in {latest}")
