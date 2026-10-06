"""Cron path migration preserves all unrelated jobs and scheduling choices."""

# ruff: noqa: PT009, PT027

from pathlib import Path

from scripts.backup import schedule
from scripts.backup.common import DEFAULT_KOPIA_SOURCE, DEFAULT_KOPIA_VOLUMES_SOURCE, BackupError
from tests.backup.support import BackupTestCase


class BackupScheduleTests(BackupTestCase):
    def test_cron_configuration_preserves_unrelated_jobs(self) -> None:
        settings = schedule.Schedule("myhost", "00:05", "03:00", 7, DEFAULT_KOPIA_SOURCE)
        entries = schedule.cron_entries(settings, Path("/usr/bin/python3"), self.root)
        original = "@daily my-other-job # keep-me\n0 4 * * * obsolete # managed:infra-db-backup-export\n"
        updated = schedule.update_crontab(original, entries)
        self.assertIn("@daily my-other-job # keep-me", updated)
        self.assertNotIn("obsolete", updated)
        self.assertIn(str(self.root / "scripts/backup/run.py"), updated)
        self.assertNotIn("scripts/backup-db.py", updated)
        self.assertIn("--run-all", updated)
        self.assertIn("--prune-all --keep-local 7", updated)
        self.assertIn(f"--kopia-source {DEFAULT_KOPIA_SOURCE}", updated)
        self.assertIn(f"--kopia-volumes-source {DEFAULT_KOPIA_VOLUMES_SOURCE}", updated)
        self.assertIn(f"15 1 * * * umask 077; /usr/bin/python3 {self.root / 'scripts/backup/latest.py'}", updated)
        self.assertEqual(len(entries), 3)
        self.assertEqual(schedule.update_crontab(updated, entries), updated)
        with self.assertRaises(BackupError):
            schedule.cron_entries(schedule.Schedule("myhost", "25:00", "03:00", 7, DEFAULT_KOPIA_SOURCE))

    def test_snapshot_job_can_be_rescheduled_and_removed(self) -> None:
        settings = schedule.Schedule("myhost", "00:05", "03:00", 7, DEFAULT_KOPIA_SOURCE, snapshot_time="02:10")
        entries = schedule.cron_entries(settings)
        self.assertTrue(entries[2].startswith("10 2 * * *"))
        installed = schedule.update_crontab("@daily unrelated\n", entries)
        self.assertEqual(schedule.update_crontab(installed, []), "@daily unrelated\n")
