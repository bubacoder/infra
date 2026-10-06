"""Check native Home Assistant recovery artifacts and fail-closed publication."""

# ruff: noqa: PT009, PT027

import contextlib
import io
import json
import sqlite3
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.backup import config, runner
from scripts.backup.apps import homeassistant as backup_homeassistant
from scripts.backup.common import BackupError


class HomeAssistantBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.export_root = self.root / "exports"
        self.archive = self.root / "native.tar"
        self.required = ["data/configuration.yaml", "data/.storage/auth", "data/home-assistant_v2.db"]
        self.target = {
            "engine": "homeassistant",
            "data": "homeassistant",
            "token_file": "homeassistant/backup-token",
            "required_files": self.required,
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_backup(self, *, omit_auth: bool = False, protected: bool = False) -> None:
        database = self.root / "recorder.db"
        with contextlib.closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS states (id integer)")
            connection.execute("INSERT INTO states VALUES (1)")
        files = {"data/configuration.yaml": b"default_config:\n", "data/home-assistant_v2.db": database.read_bytes()}
        if not omit_auth:
            files["data/.storage/auth"] = b'{"data": {"users": []}}'
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w:gz") as tar:
            for name, contents in files.items():
                member = tarfile.TarInfo(name)
                member.size = len(contents)
                tar.addfile(member, io.BytesIO(contents))
        metadata = {"slug": "fixture", "protected": protected, "homeassistant": {"exclude_database": False, "version": "2026.9.3"}}
        with tarfile.open(self.archive, "w") as tar:
            for name, contents in {"./backup.json": json.dumps(metadata).encode(), "./homeassistant.tar.gz": payload.getvalue()}.items():
                member = tarfile.TarInfo(name)
                member.size = len(contents)
                tar.addfile(member, io.BytesIO(contents))

    def test_native_archive_produces_standalone_recorder_and_private_export(self) -> None:
        self.make_backup()
        with patch.object(backup_homeassistant, "create_backup", return_value=self.archive):
            export = backup_homeassistant.export("automation/homeassistant", self.target, self.root, self.export_root)
        self.assertFalse(self.archive.exists())
        self.assertEqual({p.name for p in export.iterdir()}, {"homeassistant.tar", "database.sqlite3", "manifest.json"})
        self.assertEqual(runner.verify_latest("automation/homeassistant", self.target, self.root, self.export_root), export)
        self.assertEqual(export.stat().st_mode & 0o777, 0o700)
        self.assertEqual((export / "homeassistant.tar").stat().st_mode & 0o777, 0o600)

    def test_missing_auth_or_encrypted_backup_never_publishes_and_preserves_native(self) -> None:
        for arguments in ({"omit_auth": True}, {"protected": True}):
            self.make_backup(**arguments)
            with patch.object(backup_homeassistant, "create_backup", return_value=self.archive), self.assertRaises(BackupError):
                backup_homeassistant.export("automation/homeassistant", self.target, self.root, self.export_root)
            self.assertTrue(self.archive.exists())
            self.assertEqual([p.name for p in (self.export_root / "automation-homeassistant").iterdir()], [".lock"])

    def test_token_permissions_are_checked_before_any_api_call(self) -> None:
        token = self.root / "token"
        token.write_text("fixture-not-a-real-token")
        token.chmod(0o644)
        with (
            patch.object(backup_homeassistant.urllib.request, "urlopen") as request,
            self.assertRaises(backup_homeassistant.HomeAssistantBackupError),
        ):
            backup_homeassistant.create_backup(self.root, token)
        request.assert_not_called()

    def test_schedule_enables_native_target_only_when_provisioned_and_does_not_silently_drop_it(self) -> None:
        with patch.object(config, "ROOT", self.root):
            self.assertNotIn("automation/homeassistant", config.configured_services("test", self.export_root))
            token = self.root / "config/docker/test/homeassistant/backup-token"
            token.parent.mkdir(parents=True)
            token.write_text("fixture")
            self.assertIn("automation/homeassistant", config.configured_services("test", self.export_root))
            (self.export_root / "automation-homeassistant").mkdir(parents=True)
            token.unlink()
            self.assertIn("automation/homeassistant", config.configured_services("test", self.export_root))
