"""Publish a pinned, self-contained Open WebUI embedding model for offline recovery."""

import contextlib
import fcntl
import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import tarfile
import tempfile
from pathlib import Path

from ..common import BackupError
from ..db import sqlite

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_FILES = (
    "config.json",
    "config_sentence_transformers.json",
    "model.safetensors",
    "modules.json",
    "sentence_bert_config.json",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.txt",
    "1_Pooling/config.json",
    "README.md",  # Preserve the upstream model card and license declaration.
)


class ModelArchiveError(ValueError):
    """The configured model or its offline recovery artifact is incomplete."""


def valid_model(config: object) -> bool:
    """Limit the first archive implementation to the tested model and pinned revision."""
    return (
        isinstance(config, dict)
        and set(config) == {"model", "revision"}
        and config["model"] == MODEL
        and isinstance(config["revision"], str)
        and re.fullmatch(r"[a-f0-9]{40}", config["revision"]) is not None
    )


def model_paths(config: dict) -> list[str]:
    """Return exact nested paths required in the paired Kopia snapshot."""
    prefix = f"offline-models/all-MiniLM-L6-v2/{config['revision']}"
    return [f"{prefix}/model.tar.gz", f"{prefix}/manifest.json"]


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_model(root: Path, config: dict) -> dict:
    """Validate every inference file inside the archive, not just its presence."""
    return verify_model_directory((root / model_paths(config)[0]).parent, config)


def verify_model_directory(directory: Path, config: dict) -> dict:
    """Check staged or published artifacts with the same validation."""
    archive, manifest_path = directory / "model.tar.gz", directory / "manifest.json"
    try:
        if archive.is_symlink() or manifest_path.is_symlink():
            raise ModelArchiveError("Offline model artifacts must be regular files")
        manifest = json.loads(manifest_path.read_text())
        if (
            manifest.get("model") != config["model"]
            or manifest.get("revision") != config["revision"]
            or archive.stat().st_size != manifest.get("archive_bytes")
            or sha256(archive) != manifest.get("archive_sha256")
        ):
            raise ModelArchiveError("Offline model identity or archive checksum mismatch")
        entries = manifest.get("files", [])
        if len(entries) != len(MODEL_FILES) or {entry["file"] for entry in entries} != set(MODEL_FILES):
            raise ModelArchiveError("Offline model file inventory is incomplete")
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            if len(members) != len(entries) or {member.name for member in members} != {f"model/{name}" for name in MODEL_FILES}:
                raise ModelArchiveError("Unexpected offline model archive members")
            for entry in entries:
                member = tar.getmember(f"model/{entry['file']}")
                if not member.isfile() or member.size != entry["bytes"]:
                    raise ModelArchiveError("Offline model archive contains a link or changed file")
                with tar.extractfile(member) as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != entry["sha256"]:
                        raise ModelArchiveError("Offline model file checksum mismatch")
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        if isinstance(error, ModelArchiveError):
            raise
        raise ModelArchiveError("Cannot validate offline model archive") from error
    return manifest


def private_dir(path: Path) -> None:
    """Never follow an existing artifact-directory symlink."""
    path.mkdir(mode=0o700, exist_ok=True)
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid():
        raise ModelArchiveError("Offline model directory must be owned by the backup user and not symlinked")
    if stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise ModelArchiveError("Offline model directory must have mode 0700")


def ensure_model(root: Path, config: dict) -> dict:
    """Archive once per revision, reusing only a fully verified existing artifact."""
    if not valid_model(config):
        raise ModelArchiveError("Invalid offline model definition")
    cache = root / "cache/embedding/models/models--sentence-transformers--all-MiniLM-L6-v2"
    if not cache.resolve().is_relative_to(root.resolve()):
        raise ModelArchiveError("Embedding cache points outside the application's data directory")
    if (cache / "refs/main").read_text().strip() != config["revision"]:
        raise ModelArchiveError("Live embedding model revision changed; update the pin and retain the previous archive")
    offline = root / "offline-models"
    private_dir(offline)
    parent = offline / "all-MiniLM-L6-v2"
    private_dir(parent)
    with (parent / ".lock").open("a+b") as lock:
        (parent / ".lock").chmod(0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        destination = parent / config["revision"]
        if destination.exists():
            private_dir(destination)
            return verify_model(root, config)
        source = cache / "snapshots" / config["revision"]
        with tempfile.TemporaryDirectory(prefix=".incomplete-", dir=parent) as temporary:
            staging = Path(temporary)
            archive = staging / "model.tar.gz"
            entries = []
            with archive.open("xb") as output:
                archive.chmod(0o600)
                with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as compressed, tarfile.open(fileobj=compressed, mode="w|") as tar:
                    for name in MODEL_FILES:
                        path = (source / name).resolve(strict=True)
                        if not path.is_relative_to(cache.resolve()) or not path.is_file():
                            raise ModelArchiveError("Model file points outside its cache or is not a regular file")
                        entry = {"file": name, "bytes": path.stat().st_size, "sha256": sha256(path)}
                        entries.append(entry)
                        info = tarfile.TarInfo(f"model/{name}")
                        info.size = entry["bytes"]
                        info.mode = 0o644
                        with path.open("rb") as stream:
                            tar.addfile(info, stream)
                output.flush()
                os.fsync(output.fileno())
            manifest = {
                **config,
                "format": "sentence-transformers-pytorch",
                "files": entries,
                "archive_bytes": archive.stat().st_size,
                "archive_sha256": sha256(archive),
            }
            manifest_path = staging / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            manifest_path.chmod(0o600)
            verify_model_directory(staging, config)
            staging.rename(destination)
        return manifest


def prune_models(root: Path, protected: set[str], keep: int = 3) -> list[str]:
    """Keep recent known-good revisions and every revision referenced by local DB exports.

    Call only after the newest DB export and its model are verified in B2.
    B2 root-snapshot retention independently preserves removed local revisions.
    """
    parent = root / "offline-models/all-MiniLM-L6-v2"
    private_dir(parent)
    with (parent / ".lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        revisions = sorted(
            (path for path in parent.iterdir() if re.fullmatch(r"[a-f0-9]{40}", path.name)),
            key=lambda path: (path.stat().st_mtime_ns, path.name),
            reverse=True,
        )
        keep_names = protected | {path.name for path in revisions[:keep]}
        removed = []
        for path in revisions:
            if path.name not in keep_names:
                private_dir(path)
                verify_model_directory(path, {"model": MODEL, "revision": path.name})
                shutil.rmtree(path)
                removed.append(path.name)
        return removed


def validate_target(service: str, target: dict, path: Path) -> None:
    if (
        service != "ai/open-webui"
        or not valid_model(target["offline_model"])
        or not set(model_paths(target["offline_model"])).issubset(target.get("paired_files", []))
    ):
        raise BackupError(f"Invalid or unpaired offline embedding model in {path}")


def check_embedding_settings(database: Path, model: dict) -> None:
    try:
        with contextlib.closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)) as connection:
            settings = dict(connection.execute("SELECT key, value FROM config WHERE key IN ('rag.embedding_model', 'rag.embedding_engine')"))
        if json.loads(settings.get("rag.embedding_model", '""')) != model["model"] or json.loads(settings.get("rag.embedding_engine", '""')) != "":
            raise BackupError("Saved embedding model/engine changed; update the offline model archive definition")
    except (sqlite3.Error, ValueError) as error:
        raise BackupError("Cannot validate saved embedding model settings") from error


def export(service: str, target: dict, volumes: Path, export_root: Path) -> Path:
    if "offline_model" not in target:
        return sqlite.export(service, target, volumes, export_root)

    def prepare(database: Path) -> dict:
        check_embedding_settings(database, target["offline_model"])
        try:
            ensure_model(volumes / target["paired_root"], target["offline_model"])
        except (ModelArchiveError, OSError) as error:
            raise BackupError(f"Offline embedding archive unavailable: {error}") from error
        return {"offline_model": target["offline_model"]}

    return sqlite.export(service, target, volumes, export_root, prepare=prepare)


def verify_offline_model(manifest: dict, target: dict, volumes: Path, latest: Path) -> None:
    if "offline_model" not in target:
        return
    if manifest.get("offline_model") != target["offline_model"]:
        raise BackupError(f"Offline model missing or changed in {latest}")
    try:
        verify_model(volumes / target["paired_root"], target["offline_model"])
    except ModelArchiveError as error:
        raise BackupError(str(error)) from error


def prune_for_exports(volumes: Path, exports: list[Path]) -> None:
    """Retain model revisions only after the caller has verified recent B2 coverage."""
    manifests = [json.loads((path / "manifest.json").read_text()) for path in exports]
    protected = {manifest["offline_model"]["revision"] for manifest in manifests if "offline_model" in manifest}
    if not protected:
        return
    try:
        removed = prune_models(volumes / "open-webui", protected)
    except ModelArchiveError as error:
        raise BackupError(str(error)) from error
    if removed:
        print(f"ai/open-webui: removed {len(removed)} old local model revisions after B2 verification")
