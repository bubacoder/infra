"""Single-node full-storage snapshots, including aliases and private inventory."""

import http.client
import ipaddress
import json
import os
import re
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..common import BackupError, artifact, container_environment, staged_export


def validate_target(service: str, target: dict, path: Path) -> None:
    if service != "ai/qdrant" or set(target) != {"version", "engine", "container"} or target["container"] != "qdrant":
        raise BackupError(f"Invalid Qdrant backup definition: {path}")


class QdrantAPI:
    """Reach only the configured container; keep credentials out of subprocess args."""

    def __init__(self, container: str) -> None:
        self.key = container_environment(container, "QDRANT__SERVICE__API_KEY")
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
            address = json.loads(result.stdout)["proxy"]["IPAddress"]
            # Docker supplies the address; accept an IPv4 literal, not a URL/hostname.
            self.base = f"http://{ipaddress.IPv4Address(address)}:6333"
        except (subprocess.SubprocessError, ValueError, KeyError, TypeError) as error:
            raise BackupError("Cannot resolve Qdrant container on its proxy network") from error
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def open(self, method: str, path: str):
        request = urllib.request.Request(self.base + path, headers={"api-key": self.key}, method=method)  # noqa: S310 - Docker-supplied IPv4, fixed HTTP port
        try:
            return self.opener.open(request, timeout=600)
        except (urllib.error.URLError, TimeoutError) as error:
            raise BackupError(f"Qdrant {method} request failed; check container/API access") from error

    def json(self, method: str, path: str):
        try:
            with self.open(method, path) as response:
                document = json.load(response)
            if document.get("status", "ok") != "ok":
                raise BackupError("Qdrant API reported failure")
            return document.get("result", document)
        except (ValueError, TypeError, AttributeError) as error:
            raise BackupError("Invalid Qdrant API response") from error

    def download(self, path: str, destination: Path) -> None:
        try:
            with self.open("GET", path) as response, destination.open("xb") as output:
                destination.chmod(0o600)
                shutil.copyfileobj(response, output)
                output.flush()
                os.fsync(output.fileno())
        except (OSError, http.client.HTTPException) as error:
            raise BackupError("Qdrant snapshot download failed") from error


def collection_path(name: str) -> str:
    return f"/collections/{urllib.parse.quote(name, safe='')}"


def inventory(api: QdrantAPI) -> dict:
    version = api.json("GET", "/")["version"]
    if api.json("GET", "/cluster").get("status") != "disabled":
        raise BackupError("Qdrant full-storage backup requires single-node, cluster-disabled mode")
    collections = {}
    for item in api.json("GET", "/collections")["collections"]:
        info = api.json("GET", collection_path(item["name"]))
        collections[item["name"]] = {"points_count": info["points_count"], "config": info["config"]}
    aliases = {item["alias_name"]: item["collection_name"] for item in api.json("GET", "/aliases")["aliases"]}
    return {"server_version": version, "cluster_status": "disabled", "collections": collections, "aliases": aliases}


def snapshot_names(api: QdrantAPI, path: str) -> set[str]:
    return {item["name"] for item in api.json("GET", path)}


def safe_snapshot_name(name: str) -> bool:
    return isinstance(name, str) and bool(re.fullmatch(r"[a-zA-Z0-9_.-]+\.snapshot", name)) and ".." not in name


def consume_tar(archive: tarfile.TarFile) -> set[str]:
    """Read complete member payloads without extracting any native paths."""
    names = set()
    for member in archive:
        if Path(member.name).is_absolute() or ".." in Path(member.name).parts or not (member.isfile() or member.isdir()):
            raise BackupError("Unsafe member in Qdrant native snapshot")
        if member.isfile():
            names.add(member.name.removeprefix("./"))
            with archive.extractfile(member) as stream:
                for _block in iter(lambda: stream.read(1024 * 1024), b""):
                    pass
    return names


def validate_snapshot(path: Path, expected: dict) -> dict:
    try:
        with tarfile.open(path, "r:") as outer:
            entries = outer.getmembers()
            members = {member.name: member for member in entries}
            with outer.extractfile("config.json") as stream:
                config = json.load(stream)
            mapping = config["collections_mapping"]
            if (
                len(entries) != len(members)
                or set(mapping) != set(expected["collections"])
                or config.get("collections_aliases", {}) != expected["aliases"]
                or len(set(mapping.values())) != len(mapping)
                or any(not safe_snapshot_name(name) for name in mapping.values())
                or set(members) != {"config.json", *mapping.values()}
                or any(not member.isfile() for member in members.values())
            ):
                raise BackupError("Qdrant snapshot collections/aliases do not match inventory")
            for name in mapping.values():
                with outer.extractfile(name) as stream, tarfile.open(fileobj=stream, mode="r|") as inner:
                    if "config.json" not in consume_tar(inner):
                        raise BackupError("Qdrant collection snapshot is missing its configuration")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, tarfile.TarError, EOFError) as error:
        raise BackupError("Invalid Qdrant full-storage snapshot") from error
    else:
        return mapping


def export(service: str, target: dict, volumes: Path, export_root: Path) -> Path:
    with staged_export(service, export_root) as run:
        api = QdrantAPI(target["container"])
        before = inventory(api)
        full_before = snapshot_names(api, "/snapshots")
        collection_before = {name: snapshot_names(api, collection_path(name) + "/snapshots") for name in before["collections"]}
        owned_full = None
        owned_collections = {}
        try:
            description = api.json("POST", "/snapshots?wait=true")
            name = description["name"]
            if not safe_snapshot_name(name) or name in full_before:
                raise BackupError("Qdrant returned an unsafe or pre-existing full snapshot name")
            owned_full = name
            archive = run.directory / "full.snapshot"
            api.download(f"/snapshots/{urllib.parse.quote(name, safe='')}", archive)
            entry = artifact(archive)
            checksum = description.get("checksum")
            if entry["bytes"] != description["size"] or entry["bytes"] == 0 or (checksum and entry["sha256"] != checksum):
                raise BackupError("Qdrant native snapshot size/checksum mismatch")
            mapping = validate_snapshot(archive, before)
            # v1.19.1 removes collection intermediates automatically. On versions
            # that retain them, delete only names confirmed by this native archive,
            # never unrelated snapshots created concurrently by an operator.
            for collection, name in mapping.items():
                if name in collection_before[collection]:
                    raise BackupError("Qdrant native archive references a pre-existing snapshot")
                if name in snapshot_names(api, collection_path(collection) + "/snapshots"):
                    owned_collections[collection] = name
            after = inventory(api)
            if before != after:
                raise BackupError("Qdrant collections/counts/config/aliases changed during capture; retry export")
            inventory_file = run.directory / "inventory.json"
            with inventory_file.open("x") as stream:
                inventory_file.chmod(0o600)
                json.dump(before, stream, indent=2)
                stream.write("\n")
            files = [entry, artifact(inventory_file)]
        finally:
            # Complete all known-owned cleanup attempts before propagating failure.
            failures = []
            paths = [f"/snapshots/{owned_full}"] if owned_full else []
            paths.extend(collection_path(collection) + "/snapshots/" + name for collection, name in owned_collections.items())
            for path in paths:
                try:
                    removed = api.json("DELETE", path + "?wait=true")
                except BackupError as error:
                    failures.append(error)
                else:
                    if removed is not True:
                        failures.append(BackupError("Qdrant snapshot cleanup failed"))
            if failures:
                raise BackupError("Could not remove exporter-owned Qdrant snapshots; refusing publication") from failures[0]
        return run.publish({"engine": "qdrant", "container": target["container"], "files": files, "server_version": before["server_version"]})


def required_files(_manifest: dict, _target: dict, _latest: Path) -> set[str]:
    return {"full.snapshot", "inventory.json"}


def verify_export(manifest: dict, _target: dict, latest: Path) -> None:
    try:
        expected = json.loads((latest / "inventory.json").read_text())
        if expected["cluster_status"] != "disabled" or expected["server_version"] != manifest["server_version"]:
            raise BackupError("Unexpected Qdrant inventory version/topology")
        validate_snapshot(latest / "full.snapshot", expected)
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise BackupError("Invalid Qdrant backup inventory") from error
