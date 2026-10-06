"""Service-local definitions and ignored host configuration, without executing dotenv."""

import re
from pathlib import Path

import yaml

from .apps import homeassistant, open_webui
from .common import ROOT, SERVICE_PART, BackupError, valid_relative_path
from .db import couchdb, mongodb, postgresql, qdrant, sqlite

BACKUP_SERVICES = (
    "tools/vaultwarden",
    "tools/guacamole",
    "dev/gitea",
    "ai/open-webui",
    "automation/n8n",
    "database/postgresql",
    "database/mongodb",
    "database/couchdb",
    "security/authentik",
    "media/photo/immich",
    "security/wg-easy",
    "ai/qdrant",
)


def load_definition(path: Path) -> dict:
    """Read the version-1 sectioned schema; legacy flat definitions are unsupported."""
    try:
        target = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as error:
        raise BackupError(f"Cannot load {path}: {error}") from error
    if (
        not isinstance(target, dict)
        or type(target.get("version")) is not int
        or target["version"] != 1
        or set(target) - {"version", "databases", "files"}
        or not ({"databases", "files"} & set(target))
    ):
        raise BackupError(f"Invalid backup definition: {path}")
    if "databases" in target:
        databases = target["databases"]
        allowed = {
            "engine",
            "container",
            "database",
            "user",
            "all_databases",
            "additional_databases",
            "storage_root",
            "writer",
            "data",
            "config",
            "token_file",
            "required_files",
        }
        if not isinstance(databases, dict) or not isinstance(databases.get("engine"), str) or set(databases) - allowed:
            raise BackupError(f"Invalid database export settings in {path}")
    if "files" in target:
        validate_files(target["files"], path)
        if "databases" not in target and set(target["files"]) != {"ignore"}:
            raise BackupError(f"Files-only manifests support only files.ignore: {path}")
    return target


def validate_files(files: object, path: Path) -> None:
    if not isinstance(files, dict) or not files or set(files) - {"root", "required", "ignore", "offline_model"}:
        raise BackupError(f"Invalid files section in {path}")
    if "ignore" in files:
        patterns = files["ignore"]
        if not isinstance(patterns, list) or any(
            not isinstance(pattern, str) or not pattern.strip() or any(char in pattern for char in "\n\r\x00") for pattern in patterns
        ):
            raise BackupError(f"Invalid files.ignore list in {path}")
    if {"root", "required"} & set(files):
        root, required = files.get("root"), files.get("required")
        if (
            not isinstance(root, str)
            or not SERVICE_PART.fullmatch(root)
            or not isinstance(required, list)
            or not required
            or any(not isinstance(item, str) or not valid_relative_path(f"{root}/{item}", root) for item in required)
        ):
            raise BackupError(f"files.root and files.required must specify valid paired application paths: {path}")
    if "offline_model" in files and ("required" not in files or not open_webui.valid_model(files["offline_model"])):
        raise BackupError(f"Invalid or unpaired files.offline_model in {path}")


def load_target(service: str, docker_dir: Path = ROOT / "docker") -> dict:
    parts = service.split("/")
    if not 2 <= len(parts) <= 3 or any(not SERVICE_PART.fullmatch(part) for part in parts):
        raise BackupError("Service must be a category/service name (or category/subcategory/service)")
    path = docker_dir.joinpath(*parts) / "backup.yaml"
    definition = load_definition(path)
    if "databases" not in definition:
        raise BackupError(f"No database/native export configured in {path}")
    # Preserve the internal adapter schema and existing stored artifact manifests.
    target = {"version": 1, **definition["databases"]}
    files = definition.get("files", {})
    for source, destination in (("root", "paired_root"), ("required", "paired_files"), ("offline_model", "offline_model")):
        if source in files:
            target[destination] = files[source]
    engine = target.get("engine")
    if engine == "sqlite":
        sqlite.validate_target(service, {key: value for key, value in target.items() if key != "offline_model"}, path)
        if "offline_model" in target:
            open_webui.validate_target(service, target, path)
    elif engine == "homeassistant":
        homeassistant.validate_target(service, target, path)
    elif engine == "qdrant":
        qdrant.validate_target(service, target, path)
    elif engine == "couchdb":
        couchdb.validate_target(service, target, path)
    elif engine == "mongodb":
        mongodb.validate_target(target, path)
    elif engine == "postgresql":
        postgresql.validate_target(target, path)
    else:
        raise BackupError(f"Unsupported backup definition: {path}")
    return target


def host_path(host: str, key: str, config_dir: Path) -> Path:
    if not SERVICE_PART.fullmatch(host):
        raise BackupError("Invalid host name")
    values = {}
    for path in (config_dir / ".env", config_dir / host / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            match = re.fullmatch(rf"\s*{key}\s*=\s*(.*?)\s*", line)
            if match:
                values[key] = match.group(1).strip("\"'")
    value = values.get(key, "")
    if not value or not Path(value).is_absolute() or "$" in value:
        raise BackupError(f"Set {key} to an absolute path in the host Docker .env")
    result = Path(value)
    if not result.is_dir():
        raise BackupError(f"{key} directory does not exist: {result}")
    return result


def docker_volumes(host: str, config_dir: Path = ROOT / "config/docker") -> Path:
    return host_path(host, "DOCKER_VOLUMES", config_dir)


def backup_root(host: str, volumes: Path, config_dir: Path = ROOT / "config/docker") -> Path:
    result = host_path(host, "DB_BACKUP_ROOT", config_dir)
    if result.is_symlink() or result.resolve().is_relative_to(volumes.resolve()):
        raise BackupError("DB_BACKUP_ROOT must be a real directory outside DOCKER_VOLUMES")
    return result


def configured_services(host: str, export_root: Path) -> tuple[str, ...]:
    if homeassistant.enabled(host, export_root, ROOT):
        return (*BACKUP_SERVICES, "automation/homeassistant")
    return BACKUP_SERVICES
