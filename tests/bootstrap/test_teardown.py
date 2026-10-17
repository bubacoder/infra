"""Teardown delegates AWS ownership and ordering to Terraform; cloud calls are mocked."""

# ruff: noqa: PT009, PT027

import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

from scripts.bootstrap import __main__ as cli
from scripts.bootstrap import config, deploy, dns, teardown
from scripts.bootstrap.core import ROOT, BootstrapError


class TeardownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        private = self.root / "config"
        private.mkdir()
        key = self.root / "operator.pub"
        key.write_text("ssh-ed25519 AAAAtest operator@test\n")
        document = yaml.safe_load((ROOT / "config-example/bootstrap-aws.yaml").read_text())
        document["vm"]["ssh_public_key"] = str(key)
        document["aws"]["admin_source_cidr"] = "8.8.8.8/32"
        document["network"]["dns"] = {"enabled": False, "verify": True}
        document["tls"]["token"] = "test-cloudflare-secret"  # noqa: S105
        source = private / "bootstrap-aws.yaml"
        deploy.atomic_write(source, yaml.safe_dump(document))
        self.config = config.load_config(source, self.root)
        self.directory = private / "terraform/bootstrap/docker-aws"
        self.runtime = self.directory / "runtime"
        self.runtime.mkdir(parents=True)
        (self.runtime / "terraform.tfstate").write_text("test state")
        (self.runtime / "main.tf").write_text("tracked guard stays intact")
        manifest = {
            "identity": {"name": "docker-aws", "aws": {"account_id": self.config.aws.account_id, "region": self.config.aws.region}},
            "public_ip": "1.2.3.4",
        }
        deploy.atomic_write(self.directory / "manifest.json", json.dumps(manifest))
        self.inventory = private / "ansible/inventory/inventory.yaml"
        deploy.atomic_write(
            self.inventory,
            "# keep comment\ndebian:\n  hosts:\n    docker-aws:\n      ansible_host: 1.2.3.4\n    keep: {}\ndocker_hosts:\n  hosts:\n    docker-aws:\n    keep:\n",
        )
        self.terraform = Mock(side_effect=self.terraform_result)
        self.plan = {
            "format_version": "1.2",
            "resource_changes": [{"mode": "managed", "address": "aws_ebs_volume.data", "change": {"actions": ["delete"]}}],
        }
        self.state = {"format_version": "1.0"}

    def terraform_result(self, plan, runner, arguments):
        if arguments == ["show", "-json", "teardown.tfplan"]:
            return json.dumps(self.plan)
        if arguments == ["show", "-json"]:
            return json.dumps(self.state)
        return ""

    def run_destroy(self, **kwargs) -> None:
        with (
            patch.object(teardown.aws, "verify_identity"),
            patch.object(teardown.aws, "terraform", self.terraform),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            teardown.destroy(self.config, Mock(), root=self.root, **kwargs)

    def test_data_consent_and_state_are_required(self) -> None:
        with self.assertRaisesRegex(BootstrapError, "DELETE_DATA"):
            self.run_destroy(assume_yes=True)
        (self.runtime / "terraform.tfstate").unlink()
        with self.assertRaisesRegex(BootstrapError, "state is missing"):
            self.run_destroy(delete_data=True, assume_yes=True)
        self.terraform.assert_not_called()

    def test_preview_does_not_apply_or_remove_files(self) -> None:
        self.run_destroy(delete_data=True, dry_run=True)
        self.assertTrue((self.runtime / "terraform.tfstate").exists())
        self.assertEqual((self.runtime / "main.tf").read_text(), "tracked guard stays intact")
        self.assertFalse((self.runtime / "bootstrap_destroy_override.tf").exists())
        self.assertFalse(any(call.args[2][0] == "apply" for call in self.terraform.call_args_list))

    def test_cancel_preserves_state_and_restores_guard(self) -> None:
        with patch("builtins.input", return_value="n"), self.assertRaisesRegex(BootstrapError, "cancelled"):
            self.run_destroy(delete_data=True)
        self.assertTrue((self.runtime / "terraform.tfstate").exists())
        self.assertFalse((self.runtime / "bootstrap_destroy_override.tf").exists())

    def test_success_applies_saved_destroy_plan_and_cleans_only_this_host(self) -> None:
        before_source = self.config.source.read_bytes()
        other = self.directory.parent / "other"
        other.mkdir()
        (other / "keep").write_text("keep")
        docker = self.root / "config/docker/docker-aws"
        docker.mkdir(parents=True)
        for name in (".env", ".env.traefik", "services.yaml", "operator.txt"):
            (docker / name).write_text("test")
        self.run_destroy(delete_data=True, assume_yes=True)
        self.assertIn(["apply", "-input=false", "-lock-timeout=30s", "teardown.tfplan"], [c.args[2] for c in self.terraform.call_args_list])
        self.assertFalse(self.directory.exists())
        self.assertEqual((docker / "operator.txt").read_text(), "test")
        self.assertFalse((docker / ".env.traefik").exists())
        self.assertEqual(self.config.source.read_bytes(), before_source)
        self.assertEqual((other / "keep").read_text(), "keep")
        self.assertEqual(self.inventory.read_text(), "# keep comment\ndebian:\n  hosts:\n    keep: {}\ndocker_hosts:\n  hosts:\n    keep:\n")

    def test_terraform_failure_preserves_recovery_files(self) -> None:
        self.terraform.side_effect = BootstrapError("Terraform failed")
        before = self.inventory.read_text()
        with self.assertRaisesRegex(BootstrapError, "Terraform failed"):
            self.run_destroy(delete_data=True, assume_yes=True)
        self.assertTrue((self.directory / "manifest.json").exists())
        self.assertEqual(self.inventory.read_text(), before)
        self.assertFalse((self.runtime / "bootstrap_destroy_override.tf").exists())

    def test_remaining_state_and_non_deletion_plan_stop_cleanup(self) -> None:
        self.state = {"format_version": "1.0", "values": {"root_module": {"resources": [{"mode": "managed"}]}}}
        with self.assertRaisesRegex(BootstrapError, "still manages"):
            self.run_destroy(delete_data=True, assume_yes=True)
        self.assertTrue((self.directory / "manifest.json").exists())
        self.plan["resource_changes"][0]["change"]["actions"] = ["create"]
        with self.assertRaisesRegex(BootstrapError, "non-deletion"):
            self.run_destroy(delete_data=True, assume_yes=True)

    def test_dns_failure_retains_state_and_inventory(self) -> None:
        with (
            patch.object(teardown.dns, "cleanup", side_effect=[None, BootstrapError("DNS failed")]),
            self.assertRaisesRegex(BootstrapError, "DNS failed"),
        ):
            self.run_destroy(delete_data=True, assume_yes=True)
        self.assertTrue((self.directory / "manifest.json").exists())
        self.assertIn("docker-aws", self.inventory.read_text())

    def test_wrong_account_or_manifest_cannot_destroy(self) -> None:
        with (
            patch.object(teardown.aws, "verify_identity", side_effect=BootstrapError("wrong account")),
            self.assertRaisesRegex(BootstrapError, "wrong account"),
        ):
            teardown.destroy(self.config, Mock(), root=self.root, delete_data=True, assume_yes=True)
        self.terraform.assert_not_called()
        deploy.atomic_write(self.directory / "manifest.json", "{}")
        with self.assertRaisesRegex(BootstrapError, "differs"):
            self.run_destroy(delete_data=True, assume_yes=True)

    def test_inventory_single_host_and_mismatch(self) -> None:
        result = teardown.remove_inventory_host("debian:\n  hosts:\n    old:\n      ansible_host: 1.2.3.4\n", "old", "1.2.3.4")
        self.assertEqual(yaml.safe_load(result), {"debian": {"hosts": {}}})
        with self.assertRaisesRegex(BootstrapError, "another host"):
            teardown.remove_inventory_host("debian:\n  hosts:\n    old:\n      ansible_host: 1.2.3.5\n", "old", "1.2.3.4")

    def test_cli_dispatch_does_not_plan_provisioning(self) -> None:
        args = argparse.Namespace(config=Path("unused"), yes=True, apply=False, destroy=True, delete_data=True, dry_run=False, show_config=False)
        with (
            patch.object(cli, "parse_args", return_value=args),
            patch.object(cli.config, "load_config", return_value=self.config),
            patch.object(cli.teardown, "destroy") as destroy,
            patch.object(cli.aws, "resolve_plan") as resolve,
        ):
            cli.main()
        destroy.assert_called_once()
        resolve.assert_not_called()

    @unittest.skipUnless(shutil.which("terraform"), "Terraform is not installed")
    def test_lifecycle_override_with_real_terraform_local_only(self) -> None:
        """Built-in terraform_data has no provider downloads or cloud resources."""
        fixture = self.root / "terraform-local-test"
        fixture.mkdir()
        main = 'resource "terraform_data" "data" {\n  input = "fixture"\n  lifecycle {\n    prevent_destroy = true\n  }\n}\n'
        (fixture / "main.tf").write_text(main)
        env = {k: v for k, v in os.environ.items() if not k.startswith("TF_")}
        env["CHECKPOINT_DISABLE"] = "1"

        def terraform(*arguments):
            return subprocess.run(
                [shutil.which("terraform"), *arguments], cwd=fixture, env=env, capture_output=True, text=True, timeout=30, check=False
            )  # noqa: S603

        self.assertEqual(terraform("init", "-backend=false", "-input=false").returncode, 0)
        self.assertEqual(terraform("apply", "-auto-approve", "-input=false").returncode, 0)
        self.assertNotEqual(terraform("plan", "-destroy", "-input=false").returncode, 0)
        (fixture / "bootstrap_destroy_override.tf").write_text(teardown.DATA_VOLUME_OVERRIDE.replace("aws_ebs_volume", "terraform_data"))
        self.assertEqual(terraform("plan", "-destroy", "-input=false", "-out=destroy.tfplan").returncode, 0)
        self.assertEqual(terraform("apply", "-input=false", "destroy.tfplan").returncode, 0)
        state = json.loads(terraform("show", "-json").stdout)
        self.assertEqual(teardown.aws.state_resources(state), [])
        self.assertEqual((fixture / "main.tf").read_text(), main)


class DnsTeardownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = Mock(target="aws")
        self.config.vm.name = "test"
        self.config.network.domain = "test.example.com"
        self.config.network.dns.cloudflare.zone = "example.com"
        self.config.network.dns.adguard = None
        self.path = self.root / "config/bootstrap-dns/test/journal.json"
        self.record = {
            "provider": "cloudflare",
            "record_id": "a" * 32,
            "path": "/zones/" + "b" * 32 + "/dns_records",
            "body": {"type": "A", "name": "test.example.com", "content": "1.2.3.4", "ttl": 1, "proxied": False},
        }
        self.journal = {
            "pending": None,
            "created": [self.record],
            "identity": {"target": "aws", "domain": "test.example.com", "cloudflare_zone": "example.com", "adguard_url": None, "address": "1.2.3.4"},
        }
        deploy.atomic_write(self.path, json.dumps(self.journal))
        self.client = Mock()
        self.client.request.return_value = {"success": True}

    def test_deletes_only_owned_id_and_updates_journal_after_readback(self) -> None:
        row = {**self.record["body"], "id": self.record["record_id"]}
        with (
            patch.object(dns, "plan_changes", return_value=([], {"cloudflare": self.client})),
            patch.object(dns, "cf_list", side_effect=[[row], [row], []]),
        ):
            dns.cleanup(self.config, execute=True, root=self.root)
        self.client.request.assert_called_once_with("DELETE", self.record["path"] + "/" + self.record["record_id"])
        self.assertEqual(dns.read_journal(self.path)["created"], [])

    def test_changed_owned_record_cannot_be_deleted(self) -> None:
        row = {**self.record["body"], "id": self.record["record_id"], "content": "5.6.7.8"}
        with (
            patch.object(dns, "plan_changes", return_value=([], {"cloudflare": self.client})),
            patch.object(dns, "cf_list", return_value=[row]),
            self.assertRaisesRegex(BootstrapError, "changed"),
        ):
            dns.cleanup(self.config, execute=True, root=self.root)
        self.client.request.assert_not_called()
        self.assertEqual(len(dns.read_journal(self.path)["created"]), 1)

    def test_replacement_record_is_not_owned_and_is_preserved(self) -> None:
        row = {**self.record["body"], "id": "c" * 32}
        with patch.object(dns, "plan_changes", return_value=([], {"cloudflare": self.client})), patch.object(dns, "cf_list", return_value=[row]):
            dns.cleanup(self.config, execute=True, root=self.root)
        self.client.request.assert_not_called()
        self.assertEqual(dns.read_journal(self.path)["created"], [])

    def test_failed_delete_retains_ownership_evidence(self) -> None:
        row = {**self.record["body"], "id": self.record["record_id"]}
        self.client.request.side_effect = BootstrapError("timeout")
        with (
            patch.object(dns, "plan_changes", return_value=([], {"cloudflare": self.client})),
            patch.object(dns, "cf_list", return_value=[row]),
            self.assertRaisesRegex(BootstrapError, "timeout"),
        ):
            dns.cleanup(self.config, execute=True, root=self.root)
        self.assertEqual(len(dns.read_journal(self.path)["created"]), 1)

    def test_preview_does_not_delete_or_rewrite_journal(self) -> None:
        before = self.path.read_bytes()
        row = {**self.record["body"], "id": self.record["record_id"]}
        with patch.object(dns, "plan_changes", return_value=([], {"cloudflare": self.client})), patch.object(dns, "cf_list", return_value=[row]):
            dns.cleanup(self.config, root=self.root)
        self.client.request.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)

    def test_adguard_removes_only_matching_rewrite(self) -> None:
        self.config.network.dns.cloudflare = None
        self.config.network.dns.adguard = Mock(url="https://dns.example.com")
        self.journal["identity"].update(cloudflare_zone=None, adguard_url="https://dns.example.com")
        body = {"domain": "test.example.com", "answer": "1.2.3.4"}
        self.journal["created"] = [{"provider": "adguard", "path": "/control/rewrite/add", "body": body, "record_id": None}]
        deploy.atomic_write(self.path, json.dumps(self.journal))
        self.client.request.side_effect = [[body], [body], None, []]
        with patch.object(dns, "plan_changes", return_value=([], {"adguard": self.client})):
            dns.cleanup(self.config, execute=True, root=self.root)
        self.assertIn(unittest.mock.call("POST", "/control/rewrite/delete", body), self.client.request.call_args_list)
        self.assertEqual(dns.read_journal(self.path)["created"], [])

    def test_pending_write_and_provider_change_stop_teardown(self) -> None:
        self.journal["pending"] = {"provider": "cloudflare"}
        deploy.atomic_write(self.path, json.dumps(self.journal))
        with self.assertRaisesRegex(BootstrapError, "uncertain"):
            dns.cleanup(self.config, execute=True, root=self.root)
        self.journal["pending"] = None
        self.journal["identity"]["domain"] = "other.example.com"
        deploy.atomic_write(self.path, json.dumps(self.journal))
        with self.assertRaisesRegex(BootstrapError, "differ"):
            dns.cleanup(self.config, execute=True, root=self.root)
        self.client.request.assert_not_called()
