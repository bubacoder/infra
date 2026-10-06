"""B2 source, age and paired-state gates before any local deletion."""

# ruff: noqa: PT009, PT027

import json
import subprocess
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from scripts.backup import kopia
from scripts.backup.common import DEFAULT_KOPIA_SOURCE, DEFAULT_KOPIA_VOLUMES_SOURCE, BackupError
from tests.backup.support import BackupTestCase


class KopiaBackupTests(BackupTestCase):
    def make_export(self, metadata: dict):
        export = self.root / "20260929T140059451373Z"
        export.mkdir()
        (export / "manifest.json").write_text(json.dumps({"created_at": "2026-09-29T14:00:59+00:00", "files": [], **metadata}))
        return export

    @staticmethod
    def snapshot_response(source=DEFAULT_KOPIA_SOURCE, root="ka123", **overrides):
        snapshot = {
            "source": {"path": source},
            "startTime": "2026-09-30T01:15:00Z",
            "endTime": "2026-09-30T01:20:00Z",
            "stats": {"errorCount": 0},
            "rootEntry": {"obj": root},
            **overrides,
        }
        return subprocess.CompletedProcess([], 0, json.dumps([snapshot]), "")

    @staticmethod
    def listing(text):
        return subprocess.CompletedProcess([], 0, text, "")

    def test_retention_waits_for_scheduled_kopia_capture(self) -> None:
        root = self.export_root
        root.mkdir(mode=0o700)
        service_dir = root / "security-authentik"
        service_dir.mkdir(mode=0o700)
        exports = []
        for day in ("01", "02", "03"):
            path = service_dir / f"202609{day}T000000000000Z"
            path.mkdir(mode=0o700)
            exports.append(path)
        other = root / "media-photo-immich"
        other.mkdir(mode=0o700)
        (other / "untouched").write_text("keep")
        with (
            patch.object(kopia, "kopia_has_export", return_value=False),
            self.assertRaisesRegex(BackupError, "No recent Kopia B2 snapshot coverage"),
        ):
            kopia.prune_local("security/authentik", self.root, self.export_root, 1)
        self.assertTrue(all(path.exists() for path in exports))
        with patch.object(kopia, "kopia_has_export", return_value=True) as confirmed:
            self.assertEqual(kopia.prune_local("security/authentik", self.root, self.export_root, 1), exports[:-1])
        confirmed.assert_called_once()
        self.assertEqual(confirmed.call_args.args, ("security/authentik", exports[-1], DEFAULT_KOPIA_SOURCE, DEFAULT_KOPIA_VOLUMES_SOURCE))
        self.assertLess(datetime.now(UTC) - confirmed.call_args.kwargs["recent_since"], timedelta(days=1, seconds=5))
        self.assertTrue(exports[-1].exists())
        self.assertEqual((other / "untouched").read_text(), "keep")

    def test_nightly_check_runs_before_local_retention_limit(self) -> None:
        root = self.export_root
        root.mkdir(mode=0o700)
        service_dir = root / "tools-vaultwarden"
        service_dir.mkdir(mode=0o700)
        export = service_dir / "20260929T000000000000Z"
        export.mkdir(mode=0o700)
        with (
            patch.object(kopia, "kopia_has_export", return_value=False),
            self.assertRaisesRegex(BackupError, "No recent Kopia B2 snapshot coverage"),
        ):
            kopia.prune_local("tools/vaultwarden", self.root, self.export_root, 7)
        self.assertTrue(export.exists())
        with patch.object(kopia, "kopia_has_export", return_value=True) as confirmed:
            self.assertEqual(kopia.prune_local("tools/vaultwarden", self.root, self.export_root, 7), [])
        confirmed.assert_called_once()

    def test_nightly_check_reports_no_completed_export(self) -> None:
        with self.assertRaisesRegex(BackupError, "No database backup root"):
            kopia.prune_local("tools/vaultwarden", self.root, self.export_root, 7)

    def test_kopia_wrong_source_or_old_snapshot_cannot_authorize_local_pruning(self) -> None:
        export = self.make_export({})
        snapshots = [
            {
                "source": {"path": "/sources/nest/docker-volumes/db-backups"},
                "endTime": "2026-09-29T15:00:00Z",
                "stats": {"errorCount": 0},
                "rootEntry": {"obj": "ka123"},
            },
            {"source": {"path": DEFAULT_KOPIA_SOURCE}, "endTime": "2026-09-29T01:20:00Z", "stats": {"errorCount": 0}, "rootEntry": {"obj": "kb123"}},
        ]
        with patch.object(kopia.subprocess, "run", return_value=self.listing(json.dumps(snapshots))) as command:
            self.assertFalse(kopia.kopia_has_export("security/authentik", export))
        command.assert_called_once()

    def test_kopia_scheduled_snapshot_with_complete_export_authorizes_retention(self) -> None:
        export = self.make_export({"engine": "postgresql", "files": [{"file": "database.dump"}, {"file": "globals.sql"}]})
        responses = [self.snapshot_response(), self.listing("database.dump\nglobals.sql\nmanifest.json\n")]
        with patch.object(kopia.subprocess, "run", side_effect=responses) as command:
            self.assertTrue(kopia.kopia_has_export("security/authentik", export))
        self.assertEqual(command.call_count, 2)
        self.assertEqual(command.call_args.args[0][-1], f"ka123/security-authentik/{export.name}")
        with patch.object(kopia.subprocess, "run", return_value=responses[0]) as command:
            self.assertFalse(kopia.kopia_has_export("security/authentik", export, recent_since=datetime.fromisoformat("2026-10-01T00:00:00+00:00")))
        command.assert_called_once()

    def test_kopia_requires_paired_vaultwarden_files_for_retention(self) -> None:
        export = self.make_export(
            {
                "engine": "sqlite",
                "database": "vaultwarden/db.sqlite3",
                "files": [{"file": "database.sqlite3"}],
                "paired_files": ["attachments", "rsa_key.pem"],
            }
        )
        responses = [
            self.snapshot_response(),
            self.listing("database.sqlite3\nmanifest.json\n"),
            self.snapshot_response(DEFAULT_KOPIA_VOLUMES_SOURCE, "kb123"),
            self.listing("attachments\n"),
        ]
        with patch.object(kopia.subprocess, "run", side_effect=responses):
            self.assertFalse(kopia.kopia_has_export("tools/vaultwarden", export))
        responses[-1] = self.listing("attachments\nrsa_key.pem\n")
        with patch.object(kopia.subprocess, "run", side_effect=responses):
            self.assertTrue(kopia.kopia_has_export("tools/vaultwarden", export))

    def test_kopia_checks_nested_gitea_paths_in_separate_application_snapshot(self) -> None:
        export = self.make_export(
            {
                "engine": "sqlite",
                "database": "gitea/gitea/gitea.db",
                "paired_root": "gitea",
                "files": [{"file": "database.sqlite3"}],
                "paired_files": ["git/repositories", "gitea/conf/app.ini", "ssh"],
            }
        )
        present = [
            self.snapshot_response(),
            self.listing("database.sqlite3\nmanifest.json\n"),
            self.snapshot_response(DEFAULT_KOPIA_VOLUMES_SOURCE, "kb123"),
            self.listing("repositories\n"),
            self.listing("app.ini\n"),
            self.listing("ssh\n"),
        ]
        with patch.object(kopia.subprocess, "run", side_effect=present) as command:
            self.assertTrue(kopia.kopia_has_export("dev/gitea", export))
        self.assertEqual(command.call_args.args[0][-1], "kb123/gitea")
        self.assertEqual(command.call_args_list[2].args[0][-1], DEFAULT_KOPIA_VOLUMES_SOURCE)
        with patch.object(kopia.subprocess, "run", side_effect=[*present[:4], self.listing("other.ini\n")]):
            self.assertFalse(kopia.kopia_has_export("dev/gitea", export))

    def test_kopia_checks_shared_postgresql_and_mattermost_in_separate_sources(self) -> None:
        export = self.make_export(
            {
                "engine": "postgresql",
                "databases": ["mattermost", "postgres"],
                "files": [{"file": "database-mattermost.dump"}, {"file": "database-postgres.dump"}, {"file": "globals.sql"}],
                "paired_root": "mattermost",
                "paired_files": ["config", "data"],
            }
        )
        responses = [
            self.snapshot_response(),
            self.listing("database-mattermost.dump\ndatabase-postgres.dump\nglobals.sql\nmanifest.json\n"),
            self.snapshot_response(DEFAULT_KOPIA_VOLUMES_SOURCE, "kb123"),
            self.listing("config\ndata\n"),
        ]
        with patch.object(kopia.subprocess, "run", side_effect=responses):
            self.assertTrue(kopia.kopia_has_export("database/postgresql", export))
        responses[-1] = self.listing("config\n")
        with patch.object(kopia.subprocess, "run", side_effect=responses):
            self.assertFalse(kopia.kopia_has_export("database/postgresql", export))

    def test_missing_stale_failed_or_wrong_paired_snapshot_blocks_model_and_export_pruning(self) -> None:
        service_dir = self.export_root / "ai-open-webui"
        service_dir.mkdir(mode=0o700, parents=True)
        self.export_root.chmod(0o700)
        latest = service_dir / "20260929T140059451373Z"
        latest.mkdir(mode=0o700)
        (latest / "manifest.json").write_text(
            json.dumps(
                {
                    "created_at": datetime.now(UTC).isoformat(),
                    "files": [{"file": "database.sqlite3"}],
                    "paired_root": "open-webui",
                    "paired_files": ["offline-models/revision/model.tar.gz"],
                }
            )
        )
        now = datetime.now(UTC).isoformat()
        export_snapshot = self.snapshot_response(startTime=now, endTime=now)
        invalid = [
            self.listing("[]"),
            self.snapshot_response(DEFAULT_KOPIA_VOLUMES_SOURCE, "kb123"),
            self.snapshot_response(DEFAULT_KOPIA_VOLUMES_SOURCE, "kb123", startTime=now, endTime=now, stats={"errorCount": 1}),
            self.snapshot_response(startTime=now, endTime=now),
            self.snapshot_response(DEFAULT_KOPIA_VOLUMES_SOURCE, "kb123", startTime=now, endTime=now, incompleteReason="canceled"),
        ]
        for paired in invalid:
            with (
                patch.object(kopia.subprocess, "run", side_effect=[export_snapshot, self.listing("database.sqlite3\nmanifest.json\n"), paired]),
                patch.object(kopia.open_webui, "prune_for_exports") as models,
                self.assertRaises(BackupError),
            ):
                kopia.prune_local("ai/open-webui", self.root, self.export_root, 1)
            models.assert_not_called()
            self.assertTrue(latest.exists())

    def test_export_snapshot_started_before_publication_is_rejected_even_if_it_ends_later(self) -> None:
        export = self.make_export({})
        with patch.object(kopia.subprocess, "run", return_value=self.snapshot_response(startTime="2026-09-29T14:00:00Z")) as command:
            self.assertFalse(kopia.kopia_has_export("security/authentik", export))
        command.assert_called_once()
