"""Offline coverage for the single private configuration and native projections."""

# ruff: noqa: PT009, PT019, PT027, S106 -- unittest mocks and explicit secret sentinels

import contextlib
import io
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts.bootstrap_config import ConfigError, Configuration, main

ROOT = Path(__file__).resolve().parents[1]


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp/opencode")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "config-example", self.root / "config-example")
        self.directory = self.root / "config/deployment"
        self.config = Configuration(self.root, self.directory, "proxmox")
        self.config.init()

    def edit(self, change):
        value = yaml.safe_load(self.config.source.read_text())
        change(value)
        self.config.source.write_text(yaml.safe_dump(value, sort_keys=False))
        return value

    def test_init_creates_one_private_file_and_preserves_edits(self):
        self.assertEqual([path.name for path in self.directory.iterdir()], ["bootstrap.yaml"])
        self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.config.source.stat().st_mode), 0o600)
        self.edit(lambda value: value["secrets"].update(cloudflare_token="SENTINEL_PRIVATE"))
        before = self.config.source.read_bytes()
        self.config.init()
        self.assertEqual(self.config.source.read_bytes(), before)

    def test_native_identity_is_derived_and_secrets_are_separated(self):
        self.edit(lambda value: value["vm"].update(name="test-host", username="tester"))
        self.edit(lambda value: value["secrets"].update(cloudflare_token="SENTINEL_PRIVATE"))
        self.config.prepare()
        host = yaml.safe_load((self.config.generated / "host.yaml").read_text())
        values = dict(line.split("=", 1) for line in (self.config.generated / "ubuntu-cloud.env").read_text().splitlines())
        self.assertEqual(host["name"], values["VMNAME"])
        self.assertEqual(host["proxmox_host"], values["PROXMOX_HOST"])
        self.assertEqual(host["proxmox_username"], values["USERNAME"])
        for name in ("host.yaml", "ubuntu-cloud.env"):
            self.assertNotIn("SENTINEL_PRIVATE", (self.config.generated / name).read_text())
        self.assertIn("SENTINEL_PRIVATE", (self.config.generated / "secrets.yaml").read_text())
        self.assertTrue(all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in self.config.generated.iterdir()))

    def test_prepare_is_repeatable_and_preserves_state_and_source(self):
        for name in ("aws.tfstate", "known_hosts", "dns-state.yaml", "storage-format-marker", "aws.tfplan"):
            (self.directory / name).write_text("KEEP")
        before = self.config.source.read_bytes()
        first = self.config.prepare()
        self.assertEqual(self.config.prepare(), first)
        self.assertEqual(self.config.source.read_bytes(), before)
        self.assertTrue(all(path.read_text() == "KEEP" for path in self.directory.iterdir() if path.is_file() and path != self.config.source))

    def test_unknown_fields_versions_targets_duplicates_and_types_fail(self):
        original = self.config.source.read_text()
        for change in (
            lambda v: v.update(version=2),
            lambda v: v.update(target="aws"),
            lambda v: v["vm"].update(secret="SENTINEL_PRIVATE"),
            lambda v: v["proxmox"].update(vmid=True),
            lambda v: v["proxmox"].update(host="-bad"),
            lambda v: v["proxmox"].update(storage="$(touch /tmp/bad)"),
            lambda v: v["proxmox"].update(memory_min_mib=8192),
            lambda v: v["dns"].update(adguard_urls=["https://user:SENTINEL_PRIVATE@dns.example"]),
            lambda v: v["dns"].update(adguard_urls=["https://@dns.example"]),
        ):
            self.config.source.write_text(original)
            self.edit(change)
            with self.assertRaises(ConfigError):
                self.config.prepare()
        self.config.source.write_text(original + "version: 1\n")
        with self.assertRaises(ConfigError):
            self.config.load()

    def test_show_config_omits_secrets_and_never_generates(self):
        self.edit(lambda v: v["secrets"].update(cloudflare_token="SENTINEL_PRIVATE"))
        output = json.dumps(self.config.show())
        self.assertNotIn("SENTINEL_PRIVATE", output)
        self.assertFalse(self.config.generated.exists())

    def test_permissions_and_symlinks_fail_without_overwriting(self):
        self.directory.chmod(0o755)
        with self.assertRaises(ConfigError):
            self.config.prepare()
        self.directory.chmod(0o700)
        self.config.source.chmod(0o644)
        with self.assertRaises(ConfigError):
            self.config.prepare()
        self.config.source.chmod(0o600)
        outside = self.root / "untouched"
        outside.write_text("KEEP")
        self.config.generated.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ConfigError):
            self.config.prepare()
        self.assertEqual(outside.read_text(), "KEEP")
        self.config.generated.unlink()
        self.config.prepare()
        destination = self.config.generated / "secrets.yaml"
        destination.unlink()
        destination.symlink_to(outside)
        with self.assertRaises(ConfigError):
            self.config.prepare()
        self.assertEqual(outside.read_text(), "KEEP")

    def test_source_symlink_and_external_directory_are_refused(self):
        original = self.config.source.read_bytes()
        self.config.source.unlink()
        other = self.root / "other"
        other.write_bytes(original)
        self.config.source.symlink_to(other)
        with self.assertRaises(ConfigError):
            self.config.show()
        with self.assertRaises(ConfigError):
            Configuration(self.root, self.root / "outside", "proxmox")

    def test_init_refuses_nonempty_directory_without_original_source(self):
        self.config.source.unlink()
        state = self.directory / "aws.tfstate"
        state.write_text("KEEP")
        with self.assertRaises(ConfigError):
            self.config.init()
        self.assertFalse(self.config.source.exists())
        self.assertEqual(state.read_text(), "KEEP")

    def aws(self):
        self.config.source.unlink()
        shutil.copy(self.root / "config-example/bootstrap-aws.yaml", self.config.source)
        self.config.source.chmod(0o600)
        self.config = Configuration(self.root, self.directory, "aws")

    @patch("scripts.bootstrap_config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
    def test_aws_json_has_no_service_secrets_and_derives_identity(self, _key):
        self.aws()
        self.edit(lambda v: v["secrets"].update(cloudflare_token="SENTINEL_PRIVATE"))
        self.config.prepare()
        text = (self.config.generated / "aws.tfvars.json").read_text()
        values = json.loads(text)
        self.assertEqual(values["vm_name"], "docker-aws")
        self.assertEqual(values["admin_user"], "ubuntu")
        self.assertEqual(values["bootstrap_mode"], "external")
        self.assertNotIn("SENTINEL_PRIVATE", text)
        self.assertFalse((self.config.generated / "ubuntu-cloud.env").exists())

    @patch("scripts.bootstrap_config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
    def test_saved_plan_binds_all_inputs_and_plan_bytes(self, _key):
        self.aws()
        plan = self.directory / "aws.tfplan"

        def native(command, **_kwargs):
            if "ACTION=plan" in command:
                plan.write_bytes(b"PLAN")
                plan.chmod(0o600)
            return subprocess.CompletedProcess(command, 0)

        with patch("scripts.bootstrap_config.subprocess.run", side_effect=native) as run:
            self.assertEqual(self.config.run("plan"), 0)
            self.assertEqual(self.config.run("apply"), 0)
            self.assertEqual(run.call_count, 2)
            self.edit(lambda v: v["host"].update(repository_ref="new-ref"))
            with self.assertRaises(ConfigError):
                self.config.run("apply")
            self.assertEqual(run.call_count, 2)
            self.config.run("plan")
            plan.write_bytes(b"CHANGED")
            with self.assertRaises(ConfigError):
                self.config.run("apply")

    @patch("scripts.bootstrap_config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
    def test_failed_plan_invalidates_previous_receipt(self, _key):
        self.aws()
        receipt = self.directory / "apply-inputs.json"
        receipt.write_text("old")
        with patch("scripts.bootstrap_config.subprocess.run", return_value=subprocess.CompletedProcess([], 1)):
            self.assertEqual(self.config.run("plan"), 1)
        self.assertFalse(receipt.exists())

    @patch("scripts.bootstrap_config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
    def test_aws_detection_preserves_operator_edits_and_retries_safely(self, _key):
        self.aws()
        self.edit(lambda v: v["secrets"].update(cloudflare_token="123456789012-203.0.113.10/32-SENTINEL_PRIVATE"))

        def detection(command, **_kwargs):
            return subprocess.CompletedProcess(command, 0, "555555555555\n" if command[0].endswith("aws") else "8.8.8.8\n", "")

        with (
            patch("scripts.bootstrap_config.executable", side_effect=lambda name: "/mock/" + name),
            patch("scripts.bootstrap_config.subprocess.run", side_effect=detection) as run,
        ):
            self.config.init()
            self.assertEqual(run.call_count, 2)
            self.config.init()
            self.assertEqual(run.call_count, 2)
        value = self.config.load()
        self.assertEqual(value["aws"]["expected_account_id"], "555555555555")
        self.assertEqual(value["aws"]["admin_source_address"], "8.8.8.8/32")
        self.assertEqual(value["secrets"]["cloudflare_token"], "123456789012-203.0.113.10/32-SENTINEL_PRIVATE")

    def test_native_dispatch_cannot_inherit_a_different_vm_identity(self):
        with (
            patch.dict(os.environ, {"VMID": "99999", "PROXMOX_HOST": "wrong-host"}),
            patch("scripts.bootstrap_config.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run,
        ):
            self.config.run("vm-wait")
        env = run.call_args.kwargs["env"]
        self.assertNotIn("VMID", env)
        self.assertNotIn("PROXMOX_HOST", env)
        self.assertEqual(env["BOOTSTRAP_INPUT_DIR"], str(self.config.generated))

    @patch("scripts.bootstrap_config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
    def test_destroy_plan_also_requires_matching_inputs(self, _key):
        self.aws()
        plan = self.directory / "destroy.tfplan"

        def native(command, **_kwargs):
            plan.write_bytes(b"DESTROY")
            plan.chmod(0o600)
            return subprocess.CompletedProcess(command, 0)

        with patch("scripts.bootstrap_config.subprocess.run", side_effect=native) as run:
            self.config.run("destroy-plan")
            self.config.run("destroy")
            self.edit(lambda v: v["secrets"].update(cloudflare_token="SENTINEL_PRIVATE_CHANGED"))
            with self.assertRaises(ConfigError):
                self.config.run("destroy")
            self.assertEqual(run.call_count, 2)

    def test_cli_parse_errors_never_echo_private_values(self):
        self.config.source.write_text("secrets: [SENTINEL_PRIVATE\n")
        with (
            patch.dict(os.environ, {"BOOTSTRAP_TARGET": "proxmox", "BOOTSTRAP_DIR": str(self.directory)}),
            patch("scripts.bootstrap_config.ROOT", self.root),
            patch("sys.argv", ["bootstrap_config.py", "show-config"]),
        ):
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                self.assertEqual(main(), 1)
            self.assertNotIn("SENTINEL_PRIVATE", output.getvalue())

    @unittest.skipUnless(shutil.which("task"), "Task is not installed")
    def test_task_initialization_and_helper_prepare_before_native_dotenv(self):
        shutil.copytree(ROOT / "scripts", self.root / "scripts")
        (self.root / "ansible").mkdir()
        shutil.copy(ROOT / "ansible/Taskfile.bootstrap.yaml", self.root / "ansible/Taskfile.bootstrap.yaml")
        (self.root / "Taskfile.yaml").write_text("version: '3'\nincludes:\n  bootstrap: ./ansible/Taskfile.bootstrap.yaml\n")
        binary = self.root / "bin"
        binary.mkdir()
        ssh = binary / "ssh"
        ssh.write_text("#!/bin/sh\ncat >/dev/null\nexit 0\n")
        ssh.chmod(0o700)
        rsync = binary / "rsync"
        rsync.write_text("#!/bin/sh\nexit 0\n")
        rsync.chmod(0o700)
        env = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]}
        result = subprocess.run(  # noqa: S603 -- isolated offline Task fixture
            [shutil.which("task"), "bootstrap:init", "TARGET=proxmox", "BOOTSTRAP_CONFIG_DIR=config/fresh"],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([path.name for path in (self.root / "config/fresh").iterdir()], ["bootstrap.yaml"])
        result = subprocess.run(  # noqa: S603 -- fixed Task command in an isolated offline fixture
            [shutil.which("task"), "bootstrap:vm-wait", "BOOTSTRAP_CONFIG_DIR=config/deployment"],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.config.generated / "ubuntu-cloud.env").exists())

        ansible = binary / "ansible-playbook"
        ansible.write_text(
            '#!/bin/sh\nset -eu\ntest -f "$BOOTSTRAP_INPUT_DIR/host.yaml"\n'
            'test -f "$BOOTSTRAP_INPUT_DIR/secrets.yaml"\n'
            'printf "STATE=%s\\nINPUT=%s\\nVERIFY=%s\\n" "$BOOTSTRAP_DIR" "$BOOTSTRAP_INPUT_DIR" "${BOOTSTRAP_VERIFY_ONLY:-0}"\n'
        )
        ansible.chmod(0o700)
        for action in ("configure", "verify"):
            result = subprocess.run(  # noqa: S603 -- isolated offline Task fixture
                [shutil.which("task"), f"bootstrap:{action}", "TARGET=proxmox", "BOOTSTRAP_CONFIG_DIR=config/deployment"],
                cwd=self.root,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(f"STATE={self.directory}\n", result.stdout)
            self.assertIn(f"INPUT={self.config.generated}\n", result.stdout)
            self.assertIn("VERIFY=1" if action == "verify" else "VERIFY=0", result.stdout)


if __name__ == "__main__":
    unittest.main()
