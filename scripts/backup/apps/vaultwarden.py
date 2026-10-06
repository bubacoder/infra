"""Vaultwarden attachment and signing-key inventory around the SQLite adapter."""

from pathlib import Path

from ..common import BackupError
from ..db import sqlite


def export(service: str, target: dict, volumes: Path, export_root: Path) -> Path:
    if "paired_files" in target:
        return sqlite.export(service, target, volumes, export_root)

    def prepare(_database: Path) -> dict:
        root = str(Path(target["database"]).parent)
        files = sorted(
            path.name
            for path in (volumes / root).iterdir()
            if path.name in {"attachments", "sends", "config.json"} or path.name.startswith("rsa_key.")
        )
        if not any(name.startswith("rsa_key.") for name in files):
            raise BackupError("Vaultwarden signing keys are missing from the paired-file inventory")
        return {"paired_files": files}

    return sqlite.export(service, target, volumes, export_root, prepare=prepare)
