"""PostgreSQL dump completeness, pairing and failure cleanup."""

# ruff: noqa: PT009, PT027

import hashlib
import json
import stat
from pathlib import Path
from unittest.mock import patch

from scripts.backup import runner
from scripts.backup.common import BackupError
from scripts.backup.db import postgresql
from tests.backup.support import BackupTestCase


class PostgreSQLBackupTests(BackupTestCase):
    @staticmethod
    def fake_dump(_command: list[str], destination: Path) -> dict:
        data = b"PGDMPtest" if destination.suffix == ".dump" else b"CREATE ROLE test;\n"
        destination.write_bytes(data)
        return {"file": destination.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    def test_exports_are_private_and_published_only_after_both_succeed(self) -> None:
        target = {"container": "authentik-postgresql", "database": "authentik", "user": "authentik"}

        def dump(command, destination):
            self.assertEqual(command[:5], ["docker", "exec", "--user", "postgres", "authentik-postgresql"])
            return self.fake_dump(command, destination)

        with patch.object(postgresql, "verify_archive"), patch.object(postgresql, "docker_dump", side_effect=dump) as exported:
            result = postgresql.export("security/authentik", target, self.root, self.export_root)
        self.assertEqual(exported.call_count, 2)
        self.assertEqual(stat.S_IMODE(result.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(result.stat().st_mode), 0o700)
        manifest = json.loads((result / "manifest.json").read_text())
        self.assertEqual(manifest["database"], "authentik")
        self.assertEqual({entry["file"] for entry in manifest["files"]}, {"database.dump", "globals.sql"})
        self.assertEqual(list(result.parent.glob(".incomplete-*")), [])

    def test_failed_export_never_publishes_partial_data(self) -> None:
        target = {"container": "immich-postgres", "database": "immich", "user": "immich"}

        def fail_on_globals(command, destination):
            if destination.name == "globals.sql":
                raise BackupError("roles failed")
            return self.fake_dump(command, destination)

        with (
            patch.object(postgresql, "verify_archive"),
            patch.object(postgresql, "docker_dump", side_effect=fail_on_globals),
            self.assertRaises(BackupError),
        ):
            postgresql.export("media/photo/immich", target, self.root, self.export_root)
        self.assertEqual([path.name for path in (self.export_root / "media-photo-immich").iterdir()], [".lock"])

    def test_shared_postgresql_exports_every_database_and_mattermost_state(self) -> None:
        target = {
            "engine": "postgresql",
            "container": "postgresql",
            "user": "postgres",
            "all_databases": True,
            "paired_root": "mattermost",
            "paired_files": ["config", "data"],
        }
        (self.root / "mattermost/config").mkdir(parents=True)
        (self.root / "mattermost/data").mkdir()

        def dump(command, destination):
            self.assertEqual(command[:5], ["docker", "exec", "--user", "postgres", "postgresql"])
            return self.fake_dump(command, destination)

        with (
            patch.object(postgresql, "postgresql_databases", return_value=["mattermost", "postgres", "productsearch"]),
            patch.object(postgresql, "docker_dump", side_effect=dump) as exported,
            patch.object(postgresql, "verify_archive") as verified,
        ):
            result = postgresql.export("database/postgresql", target, self.root, self.export_root)
        self.assertEqual(exported.call_count, 4)
        self.assertEqual(verified.call_count, 3)
        manifest = json.loads((result / "manifest.json").read_text())
        self.assertEqual(manifest["databases"], ["mattermost", "postgres", "productsearch"])
        self.assertEqual(manifest["paired_files"], ["config", "data"])
        self.assertEqual(
            {entry["file"] for entry in manifest["files"]},
            {"database-mattermost.dump", "database-postgres.dump", "database-productsearch.dump", "globals.sql"},
        )

    def test_n8n_dump_fails_closed_without_encryption_config(self) -> None:
        target = {
            "engine": "postgresql",
            "container": "n8n-postgres",
            "database": "n8n",
            "user": "root",
            "paired_root": "n8n",
            "paired_files": ["config", "binaryData"],
        }
        (self.root / "n8n/binaryData").mkdir(parents=True)
        with (
            patch.object(postgresql, "docker_dump", side_effect=self.fake_dump),
            patch.object(postgresql, "verify_archive"),
            self.assertRaisesRegex(BackupError, "Required application files"),
        ):
            postgresql.export("automation/n8n", target, self.root, self.export_root)
        self.assertEqual([path.name for path in (self.export_root / "automation-n8n").iterdir()], [".lock"])
        (self.root / "n8n/config").write_text("test key config")
        with patch.object(postgresql, "docker_dump", side_effect=self.fake_dump), patch.object(postgresql, "verify_archive"):
            result = postgresql.export("automation/n8n", target, self.root, self.export_root)
        manifest = json.loads((result / "manifest.json").read_text())
        self.assertEqual(manifest["paired_root"], "n8n")
        self.assertEqual(manifest["paired_files"], ["config", "binaryData"])

    def test_retry_removes_only_incomplete_export_from_same_service(self) -> None:
        target = {"container": "immich-postgres", "database": "immich", "user": "immich"}
        self.export_root.mkdir(mode=0o700)
        service_dir = self.export_root / "media-photo-immich"
        service_dir.mkdir(mode=0o700)
        stale = service_dir / ".incomplete-crashed"
        stale.mkdir(mode=0o700)
        (stale / "database.dump").write_bytes(b"partial")
        other = self.export_root / "security-authentik"
        other.mkdir(mode=0o700)
        (other / "retain.dump").write_bytes(b"keep")
        with patch.object(postgresql, "verify_archive"), patch.object(postgresql, "docker_dump", side_effect=self.fake_dump):
            postgresql.export("media/photo/immich", target, self.root, self.export_root)
        self.assertFalse(stale.exists())
        self.assertEqual((other / "retain.dump").read_bytes(), b"keep")

    def test_verify_latest_detects_corruption_without_a_live_database(self) -> None:
        target = {"engine": "postgresql", "container": "authentik-postgresql", "database": "authentik", "user": "authentik"}
        with patch.object(postgresql, "verify_archive"), patch.object(postgresql, "docker_dump", side_effect=self.fake_dump):
            directory = postgresql.export("security/authentik", target, self.root, self.export_root)
            self.assertEqual(runner.verify_latest("security/authentik", target, self.root, self.export_root), directory)
        (directory / "database.dump").write_bytes(b"BADMPtest")
        with self.assertRaisesRegex(BackupError, "Checksum mismatch"):
            runner.verify_latest("security/authentik", target, self.root, self.export_root)
