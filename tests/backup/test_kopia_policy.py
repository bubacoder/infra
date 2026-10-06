"""YAML collection and source-policy updates preserve other backup settings."""

# ruff: noqa: PT009, PT027

import copy
from unittest.mock import patch

from scripts.backup import config, kopia_policy
from scripts.backup.common import BackupError
from tests.backup.support import BackupTestCase

TARGET = "root@nest:/sources/nest/docker-volumes"


class KopiaPolicyTests(BackupTestCase):
    def test_collection_preserves_globs_and_deduplicates_policy_only_and_export_manifests(self) -> None:
        app = self.root / "media/jellyfin"
        app.mkdir(parents=True)
        (app / "backup.yaml").write_text('version: 1\nfiles:\n  ignore: ["**/log/nginx/**", jellyfin/cache]\n')
        database = self.root / "security/authentik"
        database.mkdir(parents=True)
        (database / "backup.yaml").write_text(
            "version: 1\ndatabases:\n  engine: postgresql\n  container: authentik-postgresql\n  database: authentik\n  user: authentik\n"
            'files:\n  ignore: ["**/log/nginx/**"]\n'
        )
        self.assertEqual(kopia_policy.collect_ignores(self.root), ["**/log/nginx/**", "jellyfin/cache"])
        self.assertEqual(config.load_target("security/authentik", self.root)["engine"], "postgresql")
        with self.assertRaises(BackupError):
            config.load_target("media/jellyfin", self.root)

    def test_invalid_or_missing_manifests_do_not_produce_empty_authoritative_list(self) -> None:
        with self.assertRaises(BackupError):
            kopia_policy.collect_ignores(self.root)
        path = self.root / "backup.yaml"
        for settings in ("ignore: cache", "ignore: [null]", 'ignore: [""]', "ignore: []\n  typo: true"):
            path.write_text(f"version: 1\nfiles:\n  {settings}\n")
            with self.assertRaises(BackupError):
                kopia_policy.collect_ignores(self.root)

    def policy(self) -> dict:
        return {
            "id": "old",
            "target": {"host": "nest", "userName": "root", "path": "/sources/nest/docker-volumes"},
            "files": {"ignore": ["obsolete"], "ignoreCacheDirs": True},
            "scheduling": {"timeOfDay": [{"hour": 1, "min": 20}]},
            "retention": {"keepMonthly": 6},
        }

    def test_preview_does_not_write_and_apply_replaces_removed_rules_in_one_command(self) -> None:
        before = self.policy()
        after = copy.deepcopy(before)
        after["id"] = "new"
        after["files"]["ignore"] = ["**/log/nginx/**"]
        with patch.object(kopia_policy, "read_policy", return_value=copy.deepcopy(before)), patch.object(kopia_policy, "kopia_command") as command:
            self.assertTrue(kopia_policy.synchronize(["kopia"], TARGET, ["**/log/nginx/**"]))
            command.assert_not_called()
        with (
            patch.object(kopia_policy, "read_policy", side_effect=[before, after]),
            patch.object(kopia_policy, "kopia_command") as command,
        ):
            self.assertTrue(kopia_policy.synchronize(["kopia"], TARGET, ["**/log/nginx/**"], apply=True))
            command.assert_called_once_with(["kopia"], "policy", "set", "--add-ignore=**/log/nginx/**", "--remove-ignore=obsolete", TARGET)

    def test_matching_rules_are_noop_regardless_of_order(self) -> None:
        before = self.policy()
        before["files"]["ignore"] = ["second", "first"]
        with patch.object(kopia_policy, "read_policy", return_value=before), patch.object(kopia_policy, "kopia_command") as command:
            self.assertFalse(kopia_policy.synchronize(["kopia"], TARGET, ["first", "second"], apply=True))
            command.assert_not_called()

    def test_apply_detects_other_policy_changes(self) -> None:
        before = self.policy()
        after = copy.deepcopy(before)
        after["files"]["ignore"] = []
        after["scheduling"] = {"manual": True}
        with (
            patch.object(kopia_policy, "read_policy", side_effect=[before, after]),
            patch.object(kopia_policy, "kopia_command"),
            self.assertRaises(BackupError),
        ):
            kopia_policy.synchronize(["kopia"], TARGET, [], apply=True)

    def test_source_lookup_requires_exact_existing_policy(self) -> None:
        for policies in ([], [self.policy(), self.policy()]):
            with patch.object(kopia_policy, "kopia_command", return_value=kopia_policy.json.dumps(policies)), self.assertRaises(BackupError):
                kopia_policy.read_policy(["kopia"], TARGET)
