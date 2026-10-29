"""Offline guards for reviewed Proxmox teardown; never contact a real hypervisor."""

# ruff: noqa: PT009, PT027 -- match bootstrap unittest fixtures

import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.bootstrap import proxmox_destroy as teardown

TEMP_ROOT = Path("/tmp/opencode")  # noqa: S108 -- approved harness directory


class ProxmoxDestroyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=TEMP_ROOT if TEMP_ROOT.is_dir() else None)
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "state"
        self.directory.mkdir(mode=0o700)
        (self.directory / "plans").mkdir(mode=0o700)
        self.config = {
            "target": "proxmox",
            "proxmox_host": "fixture-hypervisor",
            "proxmox_vmid": 999,
            "name": "k3s-fixture",
            "proxmox_username": "ubuntu",
            "proxmox_storage": "local-lvm",
            "proxmox_address": "192.0.2.125",
            "dns": {"enabled": False},
        }
        self.vm = {
            "name": "k3s-fixture",
            "ciuser": "ubuntu",
            "scsi0": "local-lvm:vm-999-disk-0,size=20G",
            "ide2": "local-lvm:vm-999-cloudinit,media=cdrom",
            "cicustom": "user=local:snippets/ubuntu-26.04-999-cloud-user.yaml,network=local:snippets/ubuntu-26.04-999-cloud-network.yaml",
            "net0": "virtio=12:34:56:78:90:ab,bridge=vmbr0",
            "cipassword": "SENTINEL_PRIVATE",
        }
        self.state = "status: running"
        self.exists = True
        self.backups = False
        self.snapshots = False
        self.snippets_present = True
        self.snippet_hash = "a" * 64
        self.interfaces = [{"hardware-address": "12:34:56:78:90:ab", "ip-addresses": [{"ip-address-type": "ipv4", "ip-address": "192.0.2.125"}]}]
        self.commands = []

    def remote(self, _host, *args, **_kwargs):  # noqa: PLR0911 -- explicit native command fixture
        self.commands.append(args)
        if args == ("hostname",):
            return "pve-node"
        if args[0] == "pvesh":
            if args[2].endswith("/config"):
                return json.dumps(self.vm) if self.exists else None
            return json.dumps([{"name": "current"}, *([{"name": "recovery"}] if self.snapshots else [])])
        if args[:2] == ("pvesm", "status"):
            return "Name Type Status Total\nlocal dir active 100\nlocal-lvm lvmthin active 200"
        if args[:2] == ("pvesm", "list"):
            if args[2] == "local":
                return "Volid Format Type Size VMID\n" + ("local:backup/vzdump-qemu-999.vma.zst vma.zst backup 100 999\n" if self.backups else "")
            return "Volid Format Type Size VMID\n" + (
                "local-lvm:vm-999-disk-0 raw images 100 999\nlocal-lvm:vm-999-cloudinit raw images 10 999\n" if self.exists else ""
            )
        if args[:2] == ("qm", "status"):
            return self.state
        if args[:3] == ("qm", "guest", "cmd"):
            return json.dumps(self.interfaces)
        if args[:2] == ("qm", "shutdown"):
            self.state = "status: stopped"
            return ""
        if args[:2] == ("qm", "destroy"):
            self.exists = False
            return ""
        if args[:2] == ("test", "-e") and not self.snippets_present:
            return None
        if args[0] == "sha256sum":
            return self.snippet_hash + "  " + args[-1]
        if args[0] == "rm":
            self.snippets_present = False
            return ""
        if args[0] == "test":
            return ""
        raise AssertionError(f"Unexpected native command: {args[0]}")

    def test_auto_address_accepts_wrapped_and_unwrapped_guest_interfaces(self):
        self.config.update(proxmox_address="auto", dns={"enabled": True})
        interfaces = self.interfaces
        for response in (interfaces, {"result": interfaces}):
            with self.subTest(response=response), patch.object(teardown, "remote", side_effect=self.remote):
                self.interfaces = response
                self.assertEqual(teardown.inspect(self.config)["address"], "192.0.2.125")
        for response in (None, "invalid", {}, {"result": {}}):
            with self.subTest(response=response), patch.object(teardown, "remote", side_effect=self.remote):
                self.interfaces = response
                with self.assertRaisesRegex(teardown.DestroyError, "original NIC"):
                    teardown.inspect(self.config)

    def test_reviewed_plan_destroy_and_repeatable_cleanup(self):
        with patch.object(teardown, "remote", side_effect=self.remote), patch.dict(os.environ, {"BOOTSTRAP_DELETE_DATA": "1"}):
            teardown.plan(self.config, self.directory)
            path = teardown.plan_path(self.directory)
            record = json.loads(path.read_text())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(record["name"], "k3s-fixture")
            self.assertNotIn("ciuser", record)
            self.assertNotIn("SENTINEL_PRIVATE", path.read_text())
            teardown.destroy(self.config, self.directory)
            self.assertFalse(self.exists)
            self.assertEqual(self.state, "status: stopped")
            teardown.cleanup(self.config, self.directory)
            teardown.cleanup(self.config, self.directory)
            self.assertTrue(path.exists())  # Recovery receipt is retained.

    def test_refuses_unapproved_plan_changed_identity_and_snapshots(self):
        with patch.object(teardown, "remote", side_effect=self.remote), patch.dict(os.environ, {"BOOTSTRAP_DELETE_DATA": "0"}):
            with self.assertRaises(teardown.DestroyError):
                teardown.plan(self.config, self.directory)
            with patch.dict(os.environ, {"BOOTSTRAP_DELETE_DATA": "1"}):
                self.snapshots = True
                with self.assertRaises(teardown.DestroyError):
                    teardown.plan(self.config, self.directory)
                self.snapshots = False
                teardown.plan(self.config, self.directory)
            self.vm["net0"] = "virtio=de:ad:be:ef:ca:fe,bridge=vmbr0"
            with self.assertRaisesRegex(teardown.DestroyError, "changed since review"):
                teardown.destroy(self.config, self.directory)
            self.assertNotIn(("qm", "destroy", "999", "--purge", "1"), self.commands)

    def test_backups_foreign_disks_and_protection_stop_before_destroy(self):
        with patch.object(teardown, "remote", side_effect=self.remote), patch.dict(os.environ, {"BOOTSTRAP_DELETE_DATA": "1"}):
            self.backups = True
            with self.assertRaisesRegex(teardown.DestroyError, "backups"):
                teardown.plan(self.config, self.directory)
            self.backups = False
            self.vm["protection"] = 1
            with self.assertRaisesRegex(teardown.DestroyError, "protection"):
                teardown.plan(self.config, self.directory)
            self.vm.pop("protection")
            self.vm["scsi0"] = "other:vm-999-disk-0"
            with self.assertRaisesRegex(teardown.DestroyError, "disks"):
                teardown.plan(self.config, self.directory)
            self.assertFalse(teardown.plan_path(self.directory).exists())

    def test_cleanup_refuses_reused_id_without_removing_snippets(self):
        with patch.object(teardown, "remote", side_effect=self.remote), patch.dict(os.environ, {"BOOTSTRAP_DELETE_DATA": "1"}):
            teardown.plan(self.config, self.directory)
            with self.assertRaisesRegex(teardown.DestroyError, "still exists"):
                teardown.cleanup(self.config, self.directory)
            self.assertFalse(any(args[0] == "rm" for args in self.commands))

    def test_cleanup_refuses_snippet_changed_after_destroy(self):
        with patch.object(teardown, "remote", side_effect=self.remote), patch.dict(os.environ, {"BOOTSTRAP_DELETE_DATA": "1"}):
            teardown.plan(self.config, self.directory)
            teardown.destroy(self.config, self.directory)
            self.snippet_hash = "b" * 64
            with self.assertRaisesRegex(teardown.DestroyError, "changed after review"):
                teardown.cleanup(self.config, self.directory)
            self.assertFalse(any(args[0] == "rm" for args in self.commands))

    def test_missing_vm_is_not_confused_with_provider_error(self):
        with patch.object(teardown, "executable", return_value="/mock/ssh"), patch.object(teardown.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 2, "", "Configuration file 'nodes/pve/qemu-server/999.conf' does not exist")
            self.assertIsNone(teardown.remote("fixture-hypervisor", "pvesh", "get", "/nodes/pve/qemu/999/config", allow_missing=True))
            run.return_value = subprocess.CompletedProcess([], 2, "", "Configuration file does not exist")
            self.assertIsNone(teardown.remote("fixture-hypervisor", "pvesh", "get", "/nodes/pve/qemu/999/config", allow_missing=True))
            run.return_value = subprocess.CompletedProcess([], 2, "", "permission denied")
            with self.assertRaises(teardown.DestroyError):
                teardown.remote("fixture-hypervisor", "pvesh", "get", "/nodes/pve/qemu/999/config", allow_missing=True)
            self.assertIn("StrictHostKeyChecking=yes", run.call_args.args[0])

    def test_plan_refuses_disabled_dns_with_owned_records(self):
        receipt = self.directory / "dns-state.yaml"
        receipt.write_text(json.dumps({"records": [{"provider": "adguard", "name": "example.test"}]}))
        receipt.chmod(0o600)
        with patch.object(teardown, "remote", side_effect=self.remote), patch.dict(os.environ, {"BOOTSTRAP_DELETE_DATA": "1"}):
            with self.assertRaisesRegex(teardown.DestroyError, "Owned DNS records"):
                teardown.plan(self.config, self.directory)
            self.assertEqual(self.commands, [])

    def run_main(self, *, action="plan", prepared="1", load_error=None, action_error=None):
        source = {
            "vm": {"name": self.config["name"]},
            "proxmox": {"vmid": self.config["proxmox_vmid"], "host": self.config["proxmox_host"], "storage": self.config["proxmox_storage"]},
        }
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.object(teardown.sys, "argv", ["proxmox_destroy.py", action, str(self.directory)]),
            patch.dict(os.environ, {"BOOTSTRAP_PREPARED": prepared}),
            patch.object(teardown, "Configuration") as configuration,
            patch.object(teardown, "read_yaml", return_value=self.config) as read_yaml,
            patch.object(teardown, action, side_effect=action_error) as operation,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            configuration.return_value.state = self.directory
            configuration.return_value.generated = self.directory / "generated"
            configuration.return_value.load.return_value = source
            configuration.return_value.load.side_effect = load_error
            result = teardown.main()
            if prepared == "1" and load_error is None:
                read_yaml.assert_called_once_with(self.directory / "generated/host.yaml")
        return result, stdout.getvalue(), stderr.getvalue(), operation

    def test_main_preserves_safe_teardown_diagnostics_for_each_action(self):
        for action in ("plan", "destroy", "cleanup"):
            with self.subTest(action=action):
                message = "VM snapshots or uncertain snapshot state exist; preserve recovery data."
                result, stdout, stderr, operation = self.run_main(action=action, action_error=teardown.DestroyError(message))
                self.assertEqual(result, 1)
                self.assertEqual(stdout, "")
                self.assertIn(message, stderr)
                operation.assert_called_once_with(self.config, self.directory)

    def test_main_preserves_safe_configuration_diagnostics(self):
        message = "bootstrap target does not match the selected deployment"
        result, stdout, stderr, operation = self.run_main(load_error=teardown.ConfigError(message))
        self.assertEqual(result, 1)
        self.assertEqual(stdout, "")
        self.assertIn(message, stderr)
        operation.assert_not_called()

    def test_main_reports_public_entrypoint_guard(self):
        result, stdout, stderr, operation = self.run_main(prepared="0")
        self.assertEqual(result, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Use the public bootstrap command", stderr)
        operation.assert_not_called()

    def test_main_redacts_raw_exceptions(self):
        for error_type in (OSError, ValueError, KeyError, TypeError):
            with self.subTest(error_type=error_type.__name__):
                result, stdout, stderr, _operation = self.run_main(action_error=error_type("SENTINEL_PRIVATE"))
                self.assertEqual(result, 1)
                self.assertEqual(stdout, "")
                self.assertNotIn("SENTINEL_PRIVATE", stderr)
                self.assertIn("no private values are displayed", stderr)

    def test_main_returns_success_for_completed_action(self):
        result, stdout, stderr, operation = self.run_main()
        self.assertEqual(result, 0)
        self.assertEqual(stdout + stderr, "")
        operation.assert_called_once_with(self.config, self.directory)


if __name__ == "__main__":
    unittest.main()
