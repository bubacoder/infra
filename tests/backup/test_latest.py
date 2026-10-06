"""Latest views pin immutable exports without uploading local history."""

# ruff: noqa: PT009, PT027

import fcntl
import json
import sqlite3
import subprocess
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from scripts.backup import latest, runner
from scripts.backup.common import DEFAULT_KOPIA_SOURCE, BackupError, private_directory
from scripts.backup.db import sqlite
from tests.backup.support import BackupTestCase


class LatestExportTests(BackupTestCase):
    def make_export(self, service: str, age: int = 0) -> Path:
        private_directory(self.export_root)
        service_dir = self.export_root / service.replace("/", "-")
        private_directory(service_dir)
        created = datetime.now(UTC) - timedelta(days=age)
        export = service_dir / created.strftime("%Y%m%dT%H%M%S%fZ")
        private_directory(export)
        private_directory(export / "nested")
        for name, contents in {
            "nested/database.dump": "database content",
            "manifest.json": json.dumps({"created_at": created.isoformat(), "files": [{"file": "nested/database.dump"}]}),
        }.items():
            (export / name).write_text(contents)
            (export / name).chmod(0o600)
        return export

    def prepare(self, services: tuple[str, ...] = ("tools/vaultwarden",)) -> latest.PreparedView:
        with (
            patch.object(latest.config, "configured_services", return_value=services),
            patch.object(latest.config, "load_target", return_value={}),
            patch.object(latest.runner, "verify_export", side_effect=lambda _service, _target, _volumes, export: export),
        ):
            return latest.prepare_view("localhost", self.root, self.export_root)

    def test_view_contains_only_newest_export_with_real_nested_hard_links(self) -> None:
        old = self.make_export("tools/vaultwarden", age=1)
        newest = self.make_export("tools/vaultwarden")
        view = self.prepare().path
        root_inode = view.stat().st_ino
        selected = view / "tools-vaultwarden" / newest.name
        self.assertEqual(list((view / "tools-vaultwarden").iterdir()), [selected])
        self.assertFalse((view / "tools-vaultwarden" / old.name).exists())
        for name in ("manifest.json", "nested/database.dump"):
            self.assertFalse((selected / name).is_symlink())
            self.assertEqual((selected / name).stat().st_ino, (newest / name).stat().st_ino)
        # Removing history doesn't invalidate the independent pathname in the view.
        (newest / "nested/database.dump").unlink()
        self.assertEqual((selected / "nested/database.dump").read_text(), "database content")
        replacement = self.make_export("tools/vaultwarden")
        self.prepare()
        self.assertEqual(view.stat().st_ino, root_inode)
        self.assertEqual(list((view / "tools-vaultwarden").iterdir()), [view / "tools-vaultwarden" / replacement.name])

    def test_stale_and_missing_services_do_not_block_healthy_updates(self) -> None:
        stale = self.make_export("automation/n8n", age=2)
        healthy = self.make_export("tools/vaultwarden")
        result = self.prepare(("automation/n8n", "tools/missing", "tools/vaultwarden"))
        self.assertEqual(result.included, 2)
        self.assertTrue((result.path / "automation-n8n" / stale.name / "manifest.json").exists())
        self.assertTrue((result.path / "tools-vaultwarden" / healthy.name / "manifest.json").exists())
        self.assertTrue(any("using stale verified export" in error for error in result.failures))
        self.assertTrue(any("tools/missing: omitted" in error for error in result.failures))
        self.assertEqual(list(self.export_root.glob(".latest-incomplete-*")), [])

    def test_invalid_newest_falls_back_to_older_export_while_healthy_service_advances(self) -> None:
        old = self.make_export("automation/n8n", age=2)
        invalid = self.make_export("automation/n8n")
        (invalid / "manifest.json").write_text("not JSON")
        healthy = self.make_export("tools/vaultwarden")
        result = self.prepare(("automation/n8n", "tools/vaultwarden"))
        self.assertEqual(list((result.path / "automation-n8n").iterdir()), [result.path / "automation-n8n" / old.name])
        self.assertTrue((result.path / "tools-vaultwarden" / healthy.name).exists())
        self.assertTrue(result.failures)

    def test_link_failure_does_not_leave_partial_service_in_view(self) -> None:
        self.make_export("automation/n8n")
        healthy = self.make_export("tools/vaultwarden")
        original_link = latest.os.link

        def link(source: Path, destination: Path, **kwargs: object) -> None:
            if "automation-n8n" in source.parts and source.name == "database.dump":
                raise OSError("simulated hard-link failure")
            original_link(source, destination, **kwargs)

        with patch.object(latest.os, "link", side_effect=link):
            result = self.prepare(("automation/n8n", "tools/vaultwarden"))
        self.assertFalse((result.path / "automation-n8n").exists())
        self.assertTrue((result.path / "tools-vaultwarden" / healthy.name / "manifest.json").exists())
        self.assertEqual(result.included, 1)

    def test_missing_local_history_can_use_previous_verified_view(self) -> None:
        export = self.make_export("tools/vaultwarden")
        self.prepare()
        (export / "manifest.json").unlink()
        healthy = self.make_export("tools/guacamole")
        result = self.prepare(("tools/vaultwarden", "tools/guacamole"))
        self.assertTrue((result.path / "tools-vaultwarden" / export.name / "manifest.json").exists())
        self.assertTrue((result.path / "tools-guacamole" / healthy.name).exists())
        self.assertTrue(result.failures)

    def test_no_usable_exports_preserves_previous_view_and_reports_failure(self) -> None:
        export = self.make_export("tools/vaultwarden")
        result = self.prepare()
        with self.assertRaisesRegex(BackupError, "No usable verified exports"):
            self.prepare(("tools/missing",))
        self.assertTrue((result.path / "tools-vaultwarden" / export.name / "manifest.json").exists())

    def test_corrupt_previous_view_is_not_reused_and_healthy_service_still_advances(self) -> None:
        export = self.make_export("automation/n8n")
        self.prepare(("automation/n8n",))
        (export / "manifest.json").write_text("corrupt manifest shared with previous view")
        healthy = self.make_export("tools/vaultwarden")
        result = self.prepare(("automation/n8n", "tools/vaultwarden"))
        self.assertFalse((result.path / "automation-n8n").exists())
        self.assertTrue((result.path / "tools-vaultwarden" / healthy.name).exists())
        self.assertTrue(any("automation/n8n: omitted" in error for error in result.failures))

    def test_nested_symlink_and_traversal_are_rejected(self) -> None:
        export = self.make_export("tools/vaultwarden")
        destination = self.root / "view"
        data = json.loads((export / "manifest.json").read_text())
        data["files"] = [{"file": "../outside"}]
        (export / "manifest.json").write_text(json.dumps(data))
        with self.assertRaisesRegex(BackupError, "Invalid export artifact"):
            latest.link_export(export, destination)
        data["files"] = [{"file": "linked/file"}]
        (export / "manifest.json").write_text(json.dumps(data))
        (export / "linked").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(BackupError, "Unexpected export artifact directory"):
            latest.link_export(export, self.root / "second-view")

    def test_busy_service_keeps_previous_view_and_does_not_block_other_service(self) -> None:
        export = self.make_export("tools/vaultwarden")
        self.prepare()
        healthy = self.make_export("tools/guacamole")
        with (export.parent / ".lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.prepare(("tools/vaultwarden", "tools/guacamole"))
        self.assertTrue((result.path / "tools-vaultwarden" / export.name).exists())
        self.assertTrue((result.path / "tools-guacamole" / healthy.name).exists())
        self.assertTrue(result.failures)

    def test_snapshot_holds_view_lock_until_foreground_upload_finishes(self) -> None:
        private_directory(self.export_root)
        view = self.export_root / "latest"
        prepared = latest.PreparedView(view, 12, ("automation/n8n: using stale verified export",))

        def upload(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
            self.assertEqual(command[-3:], ["snapshot", "create", DEFAULT_KOPIA_SOURCE])
            with (self.export_root / ".latest.lock").open("a+b") as lock, self.assertRaises(BlockingIOError):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return subprocess.CompletedProcess(command, 0)

        with (
            patch.object(latest.config, "docker_volumes", return_value=self.root),
            patch.object(latest.config, "backup_root", return_value=self.export_root),
            patch.object(latest, "container_command", return_value=["docker", "exec", "kopia-b2", "kopia"]),
            patch.object(latest, "check_mount"),
            patch.object(latest, "prepare_view", return_value=prepared),
            patch.object(latest.subprocess, "run", side_effect=upload),
        ):
            self.assertEqual(latest.snapshot_latest("localhost"), prepared)

    def test_cli_reports_degraded_exit_only_after_snapshot_job_returns(self) -> None:
        result = latest.PreparedView(self.export_root / "latest", 12, ("automation/n8n: omitted",))
        with (
            patch.object(latest.sys, "argv", ["latest.py"]),
            patch.object(latest, "snapshot_latest", return_value=result) as snapshot,
            self.assertRaises(SystemExit) as raised,
        ):
            latest.main()
        snapshot.assert_called_once()
        self.assertEqual(raised.exception.code, 1)

    def test_real_corrupt_export_does_not_prevent_kopia_upload_of_healthy_and_fallback_data(self) -> None:
        targets = {
            "tools/healthy": {"engine": "sqlite", "database": "healthy.sqlite3"},
            "tools/broken": {"engine": "sqlite", "database": "broken.sqlite3"},
        }
        exports = {}
        for service, target in targets.items():
            with closing(sqlite3.connect(self.root / target["database"])) as connection:
                connection.execute("CREATE TABLE records (id INTEGER)")
                connection.commit()
            exports[service] = sqlite.export(service, target, self.root, self.export_root)
        corrupt = sqlite.export("tools/broken", targets["tools/broken"], self.root, self.export_root)
        with (corrupt / "database.sqlite3").open("ab") as stream:
            stream.write(b"corruption after publication")

        def upload(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
            self.assertEqual(command[-3:], ["snapshot", "create", DEFAULT_KOPIA_SOURCE])
            view = self.export_root / "latest"
            for service, target in targets.items():
                selected = runner.verify_latest(service, target, self.root, view)
                self.assertEqual(selected.name, exports[service].name)
            self.assertFalse((view / "tools-broken" / corrupt.name).exists())
            return subprocess.CompletedProcess(command, 0)

        with (
            patch.object(latest.sys, "argv", ["latest.py"]),
            patch.object(latest.config, "docker_volumes", return_value=self.root),
            patch.object(latest.config, "backup_root", return_value=self.export_root),
            patch.object(latest.config, "configured_services", return_value=tuple(targets)),
            patch.object(latest.config, "load_target", side_effect=targets.__getitem__),
            patch.object(latest, "container_command", return_value=["docker", "exec", "kopia-b2", "kopia"]),
            patch.object(latest, "check_mount"),
            patch.object(latest.subprocess, "run", side_effect=upload) as snapshot,
            self.assertRaises(SystemExit) as raised,
        ):
            latest.main()
        self.assertEqual(raised.exception.code, 1)
        snapshot.assert_called_once()

    def test_mount_guard_rejects_history_or_writable_mount(self) -> None:
        view = self.export_root / "latest"
        for source, writable in ((self.export_root, False), (view, True), (view, False)):
            result = subprocess.CompletedProcess(
                [],
                0,
                json.dumps(
                    [
                        {"Type": "bind", "Destination": DEFAULT_KOPIA_SOURCE, "Source": str(source), "RW": writable},
                    ]
                ),
            )
            with patch.object(latest.subprocess, "run", return_value=result):
                if source == view and not writable:
                    latest.check_mount(["docker", "exec", "kopia-b2"], view, DEFAULT_KOPIA_SOURCE)
                else:
                    with self.assertRaisesRegex(BackupError, "recreate"):
                        latest.check_mount(["docker", "exec", "kopia-b2"], view, DEFAULT_KOPIA_SOURCE)
