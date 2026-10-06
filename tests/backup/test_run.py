"""Entrypoints resolve their package independently of the cron working directory."""

# ruff: noqa: PT009, PT027

import contextlib
import io
import subprocess
import sys
from unittest.mock import patch

from scripts.backup import run
from scripts.backup.common import ROOT
from tests.backup.support import BackupTestCase


class BackupCliTests(BackupTestCase):
    def test_both_entrypoints_work_outside_repository(self) -> None:
        for name in ("run.py", "schedule.py"):
            result = subprocess.run(  # noqa: S603
                [sys.executable, str(ROOT / "scripts/backup" / name), "--help"],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("usage:", result.stdout)

    def test_dry_run_does_not_export_or_prune(self) -> None:
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["run.py", "security/wg-easy", "--dry-run"]),
            patch.object(run.config, "docker_volumes", return_value=self.root),
            patch.object(run.config, "backup_root", return_value=self.export_root),
            patch.object(run.config, "load_target", return_value={"engine": "sqlite", "database": "wg-easy-v15/wg-easy.db"}),
            patch.object(run.runner, "perform_export") as export,
            patch.object(run.kopia, "prune_local") as prune,
            contextlib.redirect_stdout(output),
        ):
            run.main()
        export.assert_not_called()
        prune.assert_not_called()
        self.assertIn("db-backups/security-wg-easy", output.getvalue())

    def test_invalid_action_combination_fails_before_host_access(self) -> None:
        with (
            patch.object(sys, "argv", ["run.py", "security/authentik", "--run-all"]),
            patch.object(run.config, "docker_volumes") as volumes,
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as failure,
        ):
            run.main()
        self.assertEqual(failure.exception.code, 2)
        volumes.assert_not_called()
