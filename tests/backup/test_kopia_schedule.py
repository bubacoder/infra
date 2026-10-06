"""Separate sources get independent settings; retired source history stays intact."""

# ruff: noqa: PT009, PT027

import copy
import sys
from unittest.mock import patch

from scripts.backup import kopia_schedule
from scripts.backup.common import DEFAULT_KOPIA_SOURCE, DEFAULT_KOPIA_VOLUMES_SOURCE, BackupError
from tests.backup.support import BackupTestCase


class KopiaScheduleTests(BackupTestCase):
    def test_apply_refreshes_running_server_and_preview_does_not(self) -> None:
        for flags in ([], ["--apply"]):
            with (
                patch.object(sys, "argv", ["kopia_schedule.py", *flags]),
                patch.object(kopia_schedule, "load_settings", return_value=[]),
                patch.object(kopia_schedule, "container_command", return_value=["kopia"]),
                patch.object(kopia_schedule, "kopia_command") as command,
            ):
                kopia_schedule.main()
            if flags:
                command.assert_called_once_with(["kopia"], "server", "refresh", "--address=http://127.0.0.1:80")
            else:
                command.assert_not_called()

    def test_settings_keep_application_ignores_out_of_export_source(self) -> None:
        policies = kopia_schedule.load_settings(kopia_schedule.SETTINGS)
        with patch.object(kopia_schedule, "collect_ignores", return_value=["/postgresql/data"]) as collect:
            db = kopia_schedule.desired_fields(policies[0])
            collect.assert_not_called()
            volumes = kopia_schedule.desired_fields(policies[1])
        self.assertEqual(policies[0]["source"], DEFAULT_KOPIA_SOURCE)
        self.assertEqual(policies[1]["source"], DEFAULT_KOPIA_VOLUMES_SOURCE)
        self.assertEqual(db["files"]["ignore"], ["/*/.incomplete-*", "/*/.lock"])
        self.assertEqual(db["scheduling"], {"manual": True})
        self.assertEqual(volumes["files"]["ignore"], ["/postgresql/data"])

    def test_preview_does_not_write_and_apply_verifies_new_source(self) -> None:
        item = kopia_schedule.load_settings(kopia_schedule.SETTINGS)[0]
        target = f"root@nest:{item['source']}"
        after = kopia_schedule.desired_fields(item)
        with patch.object(kopia_schedule, "defined_policy", return_value=None), patch.object(kopia_schedule, "kopia_command") as command:
            kopia_schedule.sync_policy(["kopia"], target, item)
            command.assert_not_called()
        with patch.object(kopia_schedule, "defined_policy", side_effect=[None, after]), patch.object(kopia_schedule, "kopia_command") as command:
            kopia_schedule.sync_policy(["kopia"], target, item, apply=True)
        arguments = command.call_args.args
        self.assertIn("--manual", arguments)
        self.assertFalse(any(argument.startswith("--snapshot-time=") for argument in arguments[1:]))
        self.assertIn("--keep-annual=0", arguments)
        self.assertIn("--add-ignore=/*/.incomplete-*", arguments)
        self.assertNotIn("--clear-ignore", arguments)

    def test_retiring_policy_preserves_ignores_retention_and_unmanaged_fields(self) -> None:
        before = {
            "id": "old",
            "scheduling": {"timeOfDay": [{"hour": 1, "min": 20}]},
            "files": {"ignore": ["existing"]},
            "retention": {"keepDaily": 7},
        }
        after = copy.deepcopy(before)
        after["id"] = "new"
        after["scheduling"] = {"manual": True}
        item = {"source": "/sources/nest/docker-volumes", "manual": True}
        with patch.object(kopia_schedule, "defined_policy", side_effect=[before, after]), patch.object(kopia_schedule, "kopia_command") as command:
            kopia_schedule.sync_policy(["kopia"], "root@nest:/sources/nest/docker-volumes", item, apply=True)
        self.assertEqual(command.call_args.args[3:], ("--manual", "root@nest:/sources/nest/docker-volumes"))

    def test_switching_scheduled_source_to_manual_clears_run_missed_first(self) -> None:
        item = kopia_schedule.load_settings(kopia_schedule.SETTINGS)[0]
        before = kopia_schedule.desired_fields(item)
        before["scheduling"] = {"timeOfDay": [{"hour": 1, "min": 15}], "runMissed": True}
        after = kopia_schedule.desired_fields(item)
        target = f"root@nest:{item['source']}"
        with patch.object(kopia_schedule, "defined_policy", side_effect=[before, after]), patch.object(kopia_schedule, "kopia_command") as command:
            kopia_schedule.sync_policy(["kopia"], target, item, apply=True)
        self.assertEqual(command.call_args_list[0].args, (["kopia"], "policy", "set", "--run-missed=inherit", target))
        self.assertIn("--manual", command.call_args_list[1].args)

    def test_manual_active_policy_still_reconciles_retention_and_ignores(self) -> None:
        item = kopia_schedule.load_settings(kopia_schedule.SETTINGS)[0]
        desired = kopia_schedule.desired_fields(item)
        wrong = copy.deepcopy(desired)
        wrong["retention"]["keepMonthly"] = 99
        self.assertFalse(kopia_schedule.matches_fields(wrong, desired))
        wrong = copy.deepcopy(desired)
        wrong["files"]["ignore"] = ["/*"]
        self.assertFalse(kopia_schedule.matches_fields(wrong, desired))

    def test_settings_reject_duplicate_sources_and_wrong_application_target(self) -> None:
        path = self.root / "snapshots.yaml"
        document = {"version": 1, "policies": [{"source": DEFAULT_KOPIA_SOURCE, "manual": True}] * 2}
        path.write_text(kopia_schedule.yaml.safe_dump(document))
        with self.assertRaises(BackupError):
            kopia_schedule.load_settings(path)
        item = kopia_schedule.load_settings(kopia_schedule.SETTINGS)[1]
        item["source"] = DEFAULT_KOPIA_SOURCE
        path.write_text(kopia_schedule.yaml.safe_dump({"version": 1, "policies": [item]}))
        with self.assertRaises(BackupError):
            kopia_schedule.load_settings(path)
