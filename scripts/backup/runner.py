"""Export dispatch and artifact/manifest verification shared by CLI and tests."""

import json
import re
from pathlib import Path

from .apps import homeassistant, open_webui, vaultwarden
from .common import BackupError, artifact
from .db import couchdb, mongodb, postgresql, qdrant, sqlite

ENGINES = {"postgresql": postgresql, "sqlite": sqlite, "mongodb": mongodb, "couchdb": couchdb, "qdrant": qdrant, "homeassistant": homeassistant}


def perform_export(service: str, target: dict, volumes: Path, export_root: Path, host: str) -> Path:
    if target["engine"] == "homeassistant":
        return homeassistant.export(service, target, volumes, export_root, host)
    if target["engine"] == "sqlite" and service == "ai/open-webui":
        return open_webui.export(service, target, volumes, export_root)
    if target["engine"] == "sqlite" and service == "tools/vaultwarden":
        return vaultwarden.export(service, target, volumes, export_root)
    return ENGINES[target["engine"]].export(service, target, volumes, export_root)


def completed_exports(service_dir: Path) -> list[Path]:
    return sorted(path for path in service_dir.iterdir() if re.fullmatch(r"\d{8}T\d{12}Z", path.name) and path.is_dir())


def required_export_files(manifest: dict, target: dict, latest: Path) -> set[str]:
    return ENGINES[target["engine"]].required_files(manifest, target, latest)


def verify_latest(service: str, target: dict, volumes: Path, export_root: Path) -> Path:
    service_dir = export_root / service.replace("/", "-")
    if not service_dir.is_dir():
        raise BackupError(f"No completed backups for {service}")
    exports = completed_exports(service_dir)
    if not exports:
        raise BackupError(f"No completed backups for {service}")
    return verify_export(service, target, volumes, exports[-1])


def verify_export(service: str, target: dict, volumes: Path, latest: Path) -> Path:
    """Validate one completed export, including an older recovery candidate."""
    try:
        manifest = json.loads((latest / "manifest.json").read_text())
    except (OSError, ValueError) as error:
        raise BackupError(f"Cannot read backup manifest in {latest}") from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("service") != service
        or manifest.get("engine") != target["engine"]
        or ("database" in target and manifest.get("database") != target["database"])
    ):
        raise BackupError(f"Unexpected backup identity in {latest}")
    if target["engine"] in {"postgresql", "mongodb", "couchdb", "qdrant"} and manifest.get("container") != target["container"]:
        raise BackupError(f"Unexpected database container in {latest}")
    if target["engine"] == "sqlite" and manifest.get("additional_databases", []) != target.get("additional_databases", []):
        raise BackupError(f"Unexpected SQLite database list in {latest}")
    if service == "ai/open-webui":
        open_webui.verify_offline_model(manifest, target, volumes, latest)
    files = manifest.get("files")
    required = required_export_files(manifest, target, latest)
    if not isinstance(files, list) or {entry.get("file") for entry in files if isinstance(entry, dict)} != required:
        raise BackupError(f"Incomplete backup manifest in {latest}")
    for entry in files:
        path = latest / entry["file"]
        if not path.is_file() or path.is_symlink() or path.stat().st_size != entry.get("bytes"):
            raise BackupError(f"Missing or changed export: {path}")
        if artifact(path)["sha256"] != entry.get("sha256"):
            raise BackupError(f"Checksum mismatch: {path}")
    ENGINES[target["engine"]].verify_export(manifest, target, latest)
    return latest
