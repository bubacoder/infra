"""Read-only bootstrap status checks with mocked providers and guest access."""

# ruff: noqa: PT009, PT019, PT027 -- unittest fixtures match the bootstrap regression tests

import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts.bootstrap.config import Configuration
from scripts.bootstrap.status import StatusError, status

ROOT = Path(__file__).resolve().parents[2]
TEST_TEMP_ROOT = Path("/tmp/opencode")  # noqa: S108 -- approved harness directory


def result(output="", *, rc=0, error=""):
    return subprocess.CompletedProcess([], rc, output, error)


VM_CONFIG = "name: docker-proxmox\nciuser: admin\nscsi0: local-lvm:vm-999-disk-0\ncicustom: user=local:snippets/ubuntu-26.04-999-cloud-user.yaml\n"


class BootstrapStatusTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=TEST_TEMP_ROOT if TEST_TEMP_ROOT.is_dir() else None)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        shutil.copytree(ROOT / "ansible/roles", self.root / "ansible/roles")
        shutil.copytree(ROOT / "config-example", self.root / "config-example")
        self.directory = self.root / "config/deployment"
        self.configuration = Configuration(self.root, self.directory, "proxmox")
        self.configuration.init()
        self.edit(lambda value: value.update(roles=["debian_base", "k3s"], services=[], host={}, dns={"enabled": False}, secrets={}))

    def edit(self, change):
        value = yaml.safe_load(self.configuration.source.read_text())
        change(value)
        self.configuration.source.write_text(yaml.safe_dump(value, sort_keys=False))

    def select_aws(self):
        self.configuration = Configuration(self.root, self.directory, "aws")

        def change(value):
            value.pop("proxmox")
            value["vm"]["username"] = "ubuntu"
            value.update(target="aws", aws=yaml.safe_load((ROOT / "config-example/bootstrap-aws.yaml").read_text())["aws"])

        self.edit(change)

    def inspect(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            status(self.configuration)
        return stream.getvalue()

    @patch("scripts.bootstrap.status.ssh_status")
    def test_absent_proxmox_vm_does_not_create_artifacts(self, ssh):
        ssh.return_value = result(rc=2, error="Configuration file does not exist")
        before = self.configuration.source.read_bytes()
        self.assertIn("Proxmox VM 999: absent", self.inspect())
        self.assertEqual(self.configuration.source.read_bytes(), before)
        self.assertFalse(self.configuration.generated.exists())
        self.assertEqual(ssh.call_count, 1)

    @patch("scripts.bootstrap.status.verify")
    @patch("scripts.bootstrap.status.ssh_status")
    def test_opted_in_access_reports_controller_readiness_without_installing(self, ssh, verify):
        self.edit(lambda value: value.update(k3s={"access": {"enabled": True, "host": "192.0.2.10", "context": "k3s-test", "install_context": True}}))
        ssh.return_value = result(rc=2, error="Configuration file does not exist")
        self.assertIn("K3s controller access: ready (context k3s-test)", self.inspect())
        verify.assert_called_once()
        self.assertFalse(self.configuration.generated.exists())

    @patch("scripts.bootstrap.status.ssh_status")
    def test_existing_id_with_wrong_identity_refuses_guest_queries(self, ssh):
        ssh.side_effect = [result("status: running\n"), result("name: another-vm\nciuser: admin\n")]
        with self.assertRaisesRegex(StatusError, "identity does not match"):
            self.inspect()
        self.assertEqual(ssh.call_count, 2)

    @patch("scripts.bootstrap.status.ssh_status")
    def test_guest_agent_pending_is_bounded_and_not_a_failure(self, ssh):
        ssh.side_effect = [result("status: running\n"), result(VM_CONFIG), result(rc=255)]
        self.assertIn("Guest agent: not ready", self.inspect())
        self.assertEqual(ssh.call_count, 3)

    @patch("scripts.bootstrap.status.command")
    @patch("scripts.bootstrap.status.ssh_status")
    def test_ready_vm_uses_pinned_key_and_only_read_only_guest_checks(self, ssh, command):
        trust = self.directory / "known_hosts"
        trust.write_text("fixture")
        trust.chmod(0o600)
        self.configuration.generated.mkdir(mode=0o700)
        generated = self.configuration.generated / "host.yaml"
        generated.write_text("original-inputs\n")
        generated.chmod(0o600)
        receipt = self.directory / "apply-inputs.json"
        receipt.write_text("original-receipt\n")
        receipt.chmod(0o600)
        ssh.side_effect = [
            result("status: running\n"),
            result(VM_CONFIG + "net0: virtio=aa:bb:cc:dd:ee:ff,bridge=vmbr0\n"),
            result(
                json.dumps([{"hardware-address": "aa:bb:cc:dd:ee:ff", "ip-addresses": [{"ip-address-type": "ipv4", "ip-address": "192.0.2.10"}]}])
            ),
            result(json.dumps({"exitcode": 0, "out-data": "status: done\n"})),
        ]
        command.side_effect = [
            result("# Host 192.0.2.10 found\n"),
            result("status: done\n"),
            result("active\n"),
            result(json.dumps({"status": {"conditions": [{"type": "Ready", "status": "True"}]}})),
        ]
        before = trust.read_bytes()
        output = self.inspect()
        self.assertIn("Guest SSH: connected with pinned key", output)
        self.assertIn("K3s node Ready: True", output)
        self.assertEqual(before, trust.read_bytes())
        self.assertEqual(generated.read_text(), "original-inputs\n")
        self.assertEqual(receipt.read_text(), "original-receipt\n")
        self.assertEqual(ssh.call_count, 4)
        self.assertTrue(all("StrictHostKeyChecking=yes" in call.args[0] for call in command.call_args_list[1:]))

    @patch("scripts.bootstrap.status.command")
    @patch("scripts.bootstrap.status.ssh_status")
    def test_missing_trust_never_tries_guest_ssh(self, ssh, command):
        ssh.side_effect = [
            result("status: running\n"),
            result(VM_CONFIG + "net0: virtio=aa:bb:cc:dd:ee:ff\n"),
            result(
                json.dumps([{"hardware-address": "aa:bb:cc:dd:ee:ff", "ip-addresses": [{"ip-address-type": "ipv4", "ip-address": "192.0.2.10"}]}])
            ),
            result(json.dumps({"exitcode": 0, "out-data": "status: done\n"})),
        ]
        self.assertIn("not yet pinned", self.inspect())
        command.assert_not_called()

    @patch("scripts.bootstrap.status.command")
    @patch("scripts.bootstrap.status.ssh_status")
    def test_pinned_key_rejection_never_falls_back_to_tofu(self, ssh, command):
        trust = self.directory / "known_hosts"
        trust.write_text("fixture")
        trust.chmod(0o600)
        ssh.side_effect = [
            result("status: running\n"),
            result(VM_CONFIG + "net0: virtio=aa:bb:cc:dd:ee:ff\n"),
            result(
                json.dumps([{"hardware-address": "aa:bb:cc:dd:ee:ff", "ip-addresses": [{"ip-address-type": "ipv4", "ip-address": "192.0.2.10"}]}])
            ),
            result(json.dumps({"exitcode": 0, "out-data": "status: done\n"})),
        ]
        command.side_effect = [result("pinned-key"), result(rc=255, error="changed key, should not be printed")]
        output = self.inspect()
        self.assertIn("pinned host key rejected", output)
        self.assertNotIn("changed key", output)
        self.assertEqual(trust.read_text(), "fixture")
        self.assertEqual(command.call_count, 2)

    @patch("scripts.bootstrap.status.command")
    def test_aws_missing_state_has_no_api_or_terraform_calls(self, command):
        self.select_aws()
        self.assertIn("no local Terraform state", self.inspect())
        command.assert_not_called()

    @patch("scripts.bootstrap.status.command")
    def test_aws_wrong_account_refuses_terraform_and_instance_lookup(self, command):
        self.select_aws()
        state = self.directory / "aws.tfstate"
        state.write_text("fixture")
        state.chmod(0o600)
        command.return_value = result("000000000000\n")
        with self.assertRaisesRegex(StatusError, "account check failed"):
            self.inspect()
        self.assertEqual(command.call_count, 1)

    @patch("scripts.bootstrap.status.command")
    def test_aws_reads_only_selected_nonsecret_terraform_output(self, command):
        self.select_aws()
        state = self.directory / "aws.tfstate"
        state.write_text("fixture")
        state.chmod(0o600)
        command.side_effect = [
            result("123456789012\n"),
            result(
                json.dumps(
                    {
                        "name": "docker-proxmox",
                        "account_id": "123456789012",
                        "region": "eu-central-1",
                        "instance_id": "i-abcdef0123456789",
                        "address": "192.0.2.10",
                    }
                )
            ),
            result('["stopped"]'),
        ]
        self.assertIn("AWS instance i-abcdef0123456789 (docker-proxmox): stopped", self.inspect())
        self.assertEqual(command.call_count, 3)
        self.assertEqual(command.call_args_list[1].args[0][-4:], ["output", f"-state={state}", "-json", "bootstrap_host"])
        self.assertFalse(self.configuration.generated.exists())

    @patch("scripts.bootstrap.status.command")
    def test_aws_empty_state_reports_no_managed_resources(self, command):
        self.select_aws()
        state = self.directory / "aws.tfstate"
        state.write_text("fixture")
        state.chmod(0o600)
        command.side_effect = [result("123456789012\n"), result(rc=1), result()]
        self.assertIn("no managed resources", self.inspect())
        self.assertEqual(command.call_args_list[2].args[0][-3:], ["state", "list", f"-state={state}"])

    @patch("scripts.bootstrap.status.command")
    def test_aws_running_reports_ssm_without_creating_ssh_trust(self, command):
        self.select_aws()
        state = self.directory / "aws.tfstate"
        state.write_text("fixture")
        state.chmod(0o600)
        command.side_effect = [
            result("123456789012\n"),
            result(
                json.dumps(
                    {
                        "name": "docker-proxmox",
                        "account_id": "123456789012",
                        "region": "eu-central-1",
                        "instance_id": "i-abcdef0123456789",
                        "address": "192.0.2.10",
                    }
                )
            ),
            result('["running"]'),
            result('["Online"]'),
        ]
        output = self.inspect()
        self.assertIn("SSM: Online", output)
        self.assertIn("not yet pinned", output)
        self.assertFalse((self.directory / "known_hosts").exists())
        self.assertEqual(command.call_count, 4)


if __name__ == "__main__":
    unittest.main()
