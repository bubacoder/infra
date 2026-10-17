"""Offline tests for bootstrap inputs, safety policies and Task entry points."""

# ruff: noqa: PT009, PT027

import base64
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEST_TEMP_ROOT = Path("/tmp/opencode")  # noqa: S108 -- approved harness directory; TemporaryDirectory creates private randomized children


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible is not installed")
class NativeBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(dir=TEST_TEMP_ROOT if TEST_TEMP_ROOT.is_dir() else None)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(ROOT / "ansible/playbooks", self.root / "ansible/playbooks")
        shutil.copytree(ROOT / "config-example", self.root / "config-example")
        self.directory = self.root / "config/bootstrap"
        self.env = {**os.environ, "BOOTSTRAP_DIR": str(self.directory), "BOOTSTRAP_TARGET": "aws", "ANSIBLE_NOCOLOR": "1"}
        self.env["ANSIBLE_CONFIG"] = str(self.root / "ansible.cfg")
        (self.root / "ansible.cfg").write_text("[defaults]\nretry_files_enabled=False\n")
        self.public_key_file = self.root / "controller-key.pub"
        self.public_key = "ssh-ed25519 " + base64.b64encode(b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20" + bytes(range(32))).decode()
        self.public_key_file.write_text(self.public_key + " fixture-comment\n")
        self.env["BOOTSTRAP_SSH_PUBLIC_KEY"] = str(self.public_key_file)
        binaries = self.root / "bin"
        binaries.mkdir()
        aws = binaries / "aws"
        aws.write_text(
            "#!/bin/sh\n"
            'test "$*" = "sts get-caller-identity --query Account --output text" || exit 42\n'
            'test "${BOOTSTRAP_TEST_AWS_FAIL:-0}" = 0 || exit 42\n'
            'printf "%s\\n" "${BOOTSTRAP_TEST_ACCOUNT:-555555555555}"\n'
        )
        aws.chmod(0o700)
        self.env["PATH"] = str(binaries) + os.pathsep + os.environ["PATH"]
        # Keep tests offline while executing the actual validation and replace tasks.
        detection = self.root / "ansible/playbooks/bootstrap/init-aws.yaml"
        tasks = yaml.safe_load(detection.read_text())
        for task in tasks:
            for step in task.get("block", []):
                if "ansible.builtin.uri" in step:
                    del step["ansible.builtin.uri"]
                    del step["register"]
                    step["ansible.builtin.set_fact"] = {
                        "bootstrap_init_ip": {"content": "{{ lookup('env', 'BOOTSTRAP_TEST_IP') | default('8.8.8.8', true) }}"}
                    }
        detection.write_text(yaml.safe_dump(tasks))

    def run_play(self, name: str, *, check: bool = True, tags: str | None = None):
        result = subprocess.run(  # noqa: S603
            [
                shutil.which("ansible-playbook"),
                "-i",
                "localhost,",
                "-c",
                "local",
                str(self.root / "ansible/playbooks" / name),
                *(["--tags", tags] if tags else []),
            ],
            env=self.env,
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def initialize(self) -> None:
        self.run_play("bootstrap-init.yaml")

    def run_storage(self, *, fixture=None, directory=None, verify_only=False):
        """Execute real storage guards/receipts with mocked probes, filesystem and mount."""
        if directory is None:
            directory = Path(tempfile.mkdtemp(dir=self.root))
        volume_id = "vol-0123456789abcdef0"
        values = {
            "bootstrap_device": {"stdout": "/dev/mock-data"},
            "bootstrap_serial": {"stdout": volume_id.replace("-", "")},
            "bootstrap_filesystem": {"stdout": "", "rc": 2},
            "bootstrap_partitions": {"stdout_lines": ["mock-data"]},
            "bootstrap_volume": {
                "stdout": json.dumps(
                    {
                        "Volumes": [
                            {
                                "SnapshotId": "",
                                "Attachments": [{"InstanceId": "i-fixture", "State": "attached"}],
                                "Tags": [{"Key": "Name", "Value": "guest-data"}],
                            }
                        ]
                    }
                )
            },
            "bootstrap_signatures": {"stdout": json.dumps({"signatures": []})},
            "bootstrap_volume_facts": {"stdout_lines": ["UUID=fixture-uuid", "TYPE=ext4"]},
            "bootstrap_fstab": {"stdout": "", "rc": 1},
            "bootstrap_mounted": {"stdout": "", "rc": 1},
        }
        values.update(fixture or {})
        source = yaml.safe_load((self.root / "ansible/playbooks/bootstrap/storage.yaml").read_text())

        def mock_tasks(tasks):
            for task in tasks:
                task.pop("become", None)
                if "block" in task:
                    mock_tasks(task["block"])
                elif "ansible.builtin.command" in task:
                    del task["ansible.builtin.command"]
                    result_name = task.pop("register")
                    task["ansible.builtin.set_fact"] = {result_name: "{{ storage_fixture['" + result_name + "'] }}"}
                elif "community.general.filesystem" in task:
                    self.assertFalse(task.pop("community.general.filesystem")["force"])
                    task["block"] = [
                        {
                            "name": "Require a durable attempt marker before simulated formatting",
                            "ansible.builtin.assert": {
                                "that": "lookup('file', bootstrap_dir + '/format-' + bootstrap_aws.data_volume_id) | length > 0"
                            },
                        },
                        {
                            "name": "Record simulated formatting",
                            "ansible.builtin.copy": {"dest": str(directory / "formatted"), "content": "ext4", "mode": "0600"},
                        },
                        {
                            "name": "Simulate an interrupted formatting operation",
                            "ansible.builtin.fail": {"msg": "Simulated format failure"},
                            "when": "storage_fixture.format_fails | default(false)",
                        },
                    ]
                elif "ansible.posix.mount" in task:
                    del task["ansible.posix.mount"]
                    task["ansible.builtin.copy"] = {"dest": str(directory / "mounted"), "content": "mounted", "mode": "0600"}

        mock_tasks(source)
        play = [
            {
                "name": "Test the storage policy offline without device or provider access",
                "hosts": "localhost",
                "gather_facts": False,
                "vars": {
                    "bootstrap_dir": str(directory),
                    "bootstrap": {"name": "guest"},
                    "bootstrap_verify_only": verify_only,
                    "storage_fixture": values,
                },
                "tasks": [
                    {
                        "name": "Supply the native provider handoff",
                        "ansible.builtin.set_fact": {
                            "bootstrap_aws": {"data_volume_id": volume_id, "instance_id": "i-fixture", "region": "eu-central-1"},
                        },
                    },
                    *source,
                ],
            }
        ]
        (self.root / "ansible/playbooks/test-storage.yaml").write_text(yaml.safe_dump(play))
        return self.run_play("test-storage.yaml", check=False), directory

    def test_blank_owned_volume_is_formatted_automatically(self) -> None:
        result, directory = self.run_storage()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((directory / "formatted").exists())
        self.assertTrue((directory / "mounted").exists())
        self.assertEqual((directory / "format-vol-0123456789abcdef0").stat().st_mode & 0o777, 0o600)

    def test_obsolete_format_volume_id_is_rejected(self) -> None:
        self.initialize()
        host = self.valid_host()
        host["format_volume_id"] = "vol-obsolete"
        (self.directory / "host.yaml").write_text(yaml.safe_dump(host))
        result = self.run_play("bootstrap-check.yaml", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("format_volume_id", result.stdout)

    def test_unsafe_storage_stops_without_formatting_or_mounting(self) -> None:
        volume = {
            "SnapshotId": "",
            "Attachments": [{"InstanceId": "i-fixture", "State": "attached"}],
            "Tags": [{"Key": "Name", "Value": "guest-data"}],
        }
        cases = {
            "wrong device": {"bootstrap_serial": {"stdout": "volwrong"}},
            "partitioned": {"bootstrap_partitions": {"stdout_lines": ["mock-data", "mock-data1"]}},
            "partitioned ext4": {
                "bootstrap_partitions": {"stdout_lines": ["mock-data", "mock-data1"]},
                "bootstrap_filesystem": {"stdout": "ext4", "rc": 0},
            },
            "unknown signature": {"bootstrap_signatures": {"stdout": json.dumps({"signatures": [{"type": "gpt"}]})}},
            "probe error": {"bootstrap_filesystem": {"stdout": "", "rc": 4}},
            "other filesystem": {
                "bootstrap_filesystem": {"stdout": "xfs", "rc": 0},
                "bootstrap_volume_facts": {"stdout_lines": ["UUID=fixture-uuid", "TYPE=xfs"]},
            },
        }
        for name, change in {
            "snapshot origin": {"SnapshotId": "snap-fixture"},
            "wrong attachment": {"Attachments": [{"InstanceId": "i-other", "State": "attached"}]},
            "detached": {"Attachments": []},
            "multiple attachments": {"Attachments": volume["Attachments"] * 2},
            "attaching": {"Attachments": [{"InstanceId": "i-fixture", "State": "attaching"}]},
            "wrong tag": {"Tags": [{"Key": "Name", "Value": "other-data"}]},
        }.items():
            cases[name] = {"bootstrap_volume": {"stdout": json.dumps({"Volumes": [{**volume, **change}]})}}
        for name, fixture in cases.items():
            with self.subTest(name=name):
                result, directory = self.run_storage(fixture=fixture)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse((directory / "formatted").exists())
                self.assertFalse((directory / "mounted").exists())
                self.assertFalse((directory / "format-vol-0123456789abcdef0").exists())

    def test_interrupted_format_keeps_marker_and_refuses_retry(self) -> None:
        result, directory = self.run_storage(fixture={"format_fails": True})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Simulated format failure", result.stdout)
        marker = directory / "format-vol-0123456789abcdef0"
        before = marker.read_bytes()
        (directory / "formatted").unlink()
        result, _ = self.run_storage(directory=directory)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_bytes(), before)
        self.assertFalse((directory / "formatted").exists())
        self.assertFalse((directory / "mounted").exists())

    def test_existing_ext4_is_preserved_and_verification_never_initializes(self) -> None:
        for verify_only in (False, True):
            with self.subTest(verify_only=verify_only):
                fixture = {"bootstrap_filesystem": {"stdout": "ext4", "rc": 0}, "bootstrap_mounted": {"stdout": "fixture-uuid", "rc": 0}}
                result, directory = self.run_storage(fixture=fixture, verify_only=verify_only)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse((directory / "formatted").exists())
                self.assertEqual((directory / "mounted").exists(), not verify_only)
                self.assertEqual((directory / "format-vol-0123456789abcdef0").exists(), not verify_only)
        result, directory = self.run_storage(verify_only=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Verification requires an existing ext4", result.stdout)
        self.assertFalse((directory / "formatted").exists())
        self.assertFalse((directory / "format-vol-0123456789abcdef0").exists())

    def test_existing_ext4_with_attempt_marker_is_reused_without_reformatting(self) -> None:
        result, directory = self.run_storage()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        marker = directory / "format-vol-0123456789abcdef0"
        before = marker.read_bytes()
        (directory / "formatted").unlink()
        result, _ = self.run_storage(
            directory=directory,
            fixture={
                "bootstrap_filesystem": {"stdout": "ext4", "rc": 0},
                "bootstrap_fstab": {"stdout": "UUID=fixture-uuid", "rc": 0},
                "bootstrap_mounted": {"stdout": "fixture-uuid", "rc": 0},
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((directory / "formatted").exists())
        self.assertEqual(marker.read_bytes(), before)

    def valid_host(self) -> dict:
        value = yaml.safe_load((self.directory / "host.yaml").read_text())
        value["repository_ref"] = "a" * 40
        (self.directory / "host.yaml").write_text(yaml.safe_dump(value))
        return value

    def test_init_separates_inputs_and_never_overwrites(self) -> None:
        self.initialize()
        self.assertEqual((self.directory / "secrets.yaml").stat().st_mode & 0o777, 0o600)
        self.assertTrue((self.directory / "aws.tfvars").exists())
        (self.directory / "host.yaml").write_text("target: aws\noperator: keep\n")
        (self.directory / "secrets.yaml").write_text("operator private input")
        self.initialize()
        self.assertEqual((self.directory / "host.yaml").read_text(), "target: aws\noperator: keep\n")
        self.assertEqual((self.directory / "secrets.yaml").read_text(), "operator private input")

    def test_aws_init_detects_public_values_without_a_private_key(self) -> None:
        self.initialize()
        variables = (self.directory / "aws.tfvars").read_text()
        self.assertIn('expected_account_id  = "555555555555"', variables)
        self.assertIn('admin_source_address = "8.8.8.8/32"', variables)
        self.assertIn(f'ssh_public_key       = "{self.public_key}"', variables)
        host = yaml.safe_load((self.directory / "host.yaml").read_text())
        self.assertEqual(host["ssh_public_key"], str(self.public_key_file))
        self.assertEqual(host["ssh_private_key"], str(self.public_key_file.with_suffix("")))
        self.assertFalse(self.public_key_file.with_suffix("").exists())

    def test_completed_aws_inputs_skip_discovery_and_remain_unchanged(self) -> None:
        self.initialize()
        before = (self.directory / "aws.tfvars").read_bytes()
        self.env["BOOTSTRAP_TEST_AWS_FAIL"] = "1"
        self.env["BOOTSTRAP_TEST_IP"] = "not an IP"
        self.public_key_file.unlink()
        self.initialize()
        self.assertEqual((self.directory / "aws.tfvars").read_bytes(), before)

    def test_aws_init_only_fills_remaining_exact_placeholders(self) -> None:
        self.initialize()
        path = self.directory / "aws.tfvars"
        variables = path.read_text().replace('"555555555555"', '"666666666666"').replace('"8.8.8.8/32"', '"203.0.113.10/32"')
        path.write_text(variables)
        self.env["BOOTSTRAP_TEST_ACCOUNT"] = "777777777777"
        self.env["BOOTSTRAP_TEST_IP"] = "1.1.1.1"
        self.initialize()
        self.assertEqual(path.read_text(), variables.replace('"203.0.113.10/32"', '"1.1.1.1/32"'))

    def test_invalid_discovery_stops_before_replacing_any_placeholder(self) -> None:
        self.env["BOOTSTRAP_TEST_IP"] = "not an IP"
        result = self.run_play("bootstrap-init.yaml", check=False)
        self.assertNotEqual(result.returncode, 0)
        example = (self.root / "config-example/terraform/aws-vm/bootstrap.tfvars").read_bytes()
        self.assertEqual((self.directory / "aws.tfvars").read_bytes(), example)
        self.env["BOOTSTRAP_TEST_IP"] = "8.8.8.8"
        self.env["BOOTSTRAP_TEST_ACCOUNT"] = "not an account"
        self.assertNotEqual(self.run_play("bootstrap-init.yaml", check=False).returncode, 0)
        self.assertEqual((self.directory / "aws.tfvars").read_bytes(), example)

    def test_aws_init_rejects_missing_public_key_and_unusable_credentials(self) -> None:
        self.env["BOOTSTRAP_TEST_AWS_FAIL"] = "1"
        self.assertNotEqual(self.run_play("bootstrap-init.yaml", check=False).returncode, 0)
        self.env["BOOTSTRAP_TEST_AWS_FAIL"] = "0"
        self.public_key_file.unlink()
        self.assertNotEqual(self.run_play("bootstrap-init.yaml", check=False).returncode, 0)
        variables = (self.directory / "aws.tfvars").read_text()
        self.assertIn('"123456789012"', variables)
        self.assertIn('"203.0.113.10/32"', variables)

    def test_proxmox_initialization_never_detects_aws_account_or_public_ip(self) -> None:
        self.env["BOOTSTRAP_TARGET"] = "proxmox"
        self.env["BOOTSTRAP_TEST_AWS_FAIL"] = "1"
        self.env["BOOTSTRAP_TEST_IP"] = "not an IP"
        self.public_key_file.unlink()
        self.initialize()
        self.assertFalse((self.directory / "aws.tfvars").exists())

    def test_proxmox_init_does_not_create_aws_inputs(self) -> None:
        self.env["BOOTSTRAP_TARGET"] = "proxmox"
        self.initialize()
        self.assertFalse((self.directory / "aws.tfvars").exists())
        value = self.valid_host()
        self.assertEqual(value["target"], "proxmox")
        self.assertNotIn("cloudflare_zone", value["dns"])
        self.run_play("bootstrap-check.yaml")

    def test_generated_host_settings_only_include_the_selected_platform(self) -> None:
        proxmox_fields = {"proxmox_host", "proxmox_vmid", "proxmox_username", "proxmox_address"}
        for target in ("aws", "proxmox"):
            self.env["BOOTSTRAP_TARGET"] = target
            self.directory = self.root / f"config/bootstrap-{target}"
            self.env["BOOTSTRAP_DIR"] = str(self.directory)
            self.initialize()
            rendered = (self.directory / "host.yaml").read_text()
            host = yaml.safe_load(rendered)
            with self.subTest(target=target):
                if target == "aws":
                    self.assertFalse(proxmox_fields.intersection(host))
                    self.assertNotIn("Proxmox", rendered)
                    self.assertIn("cloudflare_zone", host["dns"])
                    self.assertNotIn("format_volume_id", rendered)
                else:
                    self.assertTrue(proxmox_fields.issubset(host))
                    self.assertNotIn("cloudflare_zone", host["dns"])
                    self.assertNotIn("format_volume_id", rendered)
                    self.assertNotIn("AWS", rendered)

    def test_no_implicit_target_in_direct_ansible_entry_points(self) -> None:
        self.env.pop("BOOTSTRAP_TARGET")
        for target in ("", "unknown"):
            self.env["BOOTSTRAP_TARGET"] = target
            for playbook in ("bootstrap-init.yaml", "bootstrap-check.yaml", "bootstrap-inspect.yaml"):
                with self.subTest(target=target, playbook=playbook):
                    result = self.run_play(playbook, check=False)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("TARGET=aws or TARGET=proxmox", result.stdout)
                    self.assertFalse(self.directory.exists())

    def test_target_mismatch_is_rejected_equally_without_modifying_inputs(self) -> None:
        for target, other in (("aws", "proxmox"), ("proxmox", "aws")):
            self.env["BOOTSTRAP_TARGET"] = target
            self.directory = self.root / f"config/bootstrap-{target}"
            self.env["BOOTSTRAP_DIR"] = str(self.directory)
            self.initialize()
            self.valid_host()
            before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
            self.env["BOOTSTRAP_TARGET"] = other
            for playbook in ("bootstrap-init.yaml", "bootstrap-check.yaml", "bootstrap-inspect.yaml"):
                with self.subTest(target=target, playbook=playbook):
                    self.assertNotEqual(self.run_play(playbook, check=False).returncode, 0)
                    self.assertEqual({path.name: path.read_bytes() for path in self.directory.iterdir()}, before)

    def test_native_spec_and_public_assertions(self) -> None:
        self.initialize()
        value = self.valid_host()
        self.run_play("bootstrap-check.yaml")
        value["repository_ref"] = "main"
        (self.directory / "host.yaml").write_text(yaml.safe_dump(value))
        self.run_play("bootstrap-check.yaml")
        value["repository_ref"] = "invalid ref"
        (self.directory / "host.yaml").write_text(yaml.safe_dump(value))
        self.assertNotEqual(self.run_play("bootstrap-check.yaml", check=False).returncode, 0)
        value["repository_ref"] = "a" * 40
        value["unknown_field"] = "not a supported input"
        (self.directory / "host.yaml").write_text(yaml.safe_dump(value))
        self.assertNotEqual(self.run_play("bootstrap-check.yaml", check=False).returncode, 0)

    def fixture_git(self, repository: Path, *arguments: str) -> str:
        result = subprocess.run(  # noqa: S603
            [
                shutil.which("git"),
                "-c",
                "user.name=Bootstrap Fixture",
                "-c",
                "user.email=bootstrap@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "core.hooksPath=/dev/null",
                *arguments,
            ],
            cwd=repository,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return result.stdout.strip()

    @unittest.skipUnless(shutil.which("git"), "Git is not installed")
    def test_sha_stays_fixed_and_branch_follows_updates_on_retry(self) -> None:
        repository = self.root / "published-repository"
        repository.mkdir()
        self.fixture_git(repository, "init", "--initial-branch=main")
        (repository / "version.txt").write_text("first\n")
        self.fixture_git(repository, "add", "version.txt")
        self.fixture_git(repository, "commit", "-m", "First fixture revision")
        first = self.fixture_git(repository, "rev-parse", "HEAD")
        checkout = yaml.safe_load((ROOT / "ansible/playbooks/bootstrap/services.yaml").read_text())[0]
        guest = self.root / "guest-checkout"
        play = [
            {
                "name": "Check native Git revision behavior",
                "hosts": "localhost",
                "gather_facts": False,
                "vars": {"bootstrap": {"repository_url": str(repository), "repository_ref": first}, "bootstrap_checkout": str(guest)},
                "tasks": [checkout],
            }
        ]
        source = self.root / "ansible/playbooks/test-repository.yaml"
        source.write_text(yaml.safe_dump(play))
        self.run_play("test-repository.yaml")
        (repository / "version.txt").write_text("fixed\n")
        self.fixture_git(repository, "commit", "-am", "Fix fixture deployment")
        second = self.fixture_git(repository, "rev-parse", "HEAD")
        self.run_play("test-repository.yaml")
        self.assertEqual(self.fixture_git(guest, "rev-parse", "HEAD"), first)
        play[0]["vars"]["bootstrap"]["repository_ref"] = "main"
        source.write_text(yaml.safe_dump(play))
        self.run_play("test-repository.yaml")
        self.assertEqual(self.fixture_git(guest, "rev-parse", "HEAD"), second)
        (repository / "version.txt").write_text("another fix\n")
        self.fixture_git(repository, "commit", "-am", "Another fixture fix")
        self.run_play("test-repository.yaml")
        self.assertEqual(self.fixture_git(guest, "rev-parse", "HEAD"), self.fixture_git(repository, "rev-parse", "HEAD"))

    def test_inspection_never_loads_secrets_or_unknown_fields(self) -> None:
        self.initialize()
        value = self.valid_host()
        value["unknown_private_field"] = "SENTINEL_DO_NOT_DISPLAY"
        value["dns"]["adguard_url"] = "https://ignored:SENTINEL_PASSWORD@adguard.example.com/path?token=SENTINEL_TOKEN"
        (self.directory / "host.yaml").write_text(yaml.safe_dump(value))
        (self.directory / "secrets.yaml").write_text("broken: [SENTINEL_PRIVATE_SECRET")
        result = self.run_play("bootstrap-inspect.yaml")
        self.assertNotIn("SENTINEL", result.stdout + result.stderr)
        self.assertIn("adguard.example.com", result.stdout)

    def test_private_parse_failures_are_censored_by_ansible(self) -> None:
        self.initialize()
        self.valid_host()
        (self.directory / "secrets.yaml").write_text("broken: [SENTINEL_PRIVATE_SECRET")
        play = [
            {
                "name": "Test private parsing",
                "hosts": "localhost",
                "gather_facts": False,
                "tasks": [
                    {"name": "Public inputs", "ansible.builtin.import_tasks": "bootstrap/inputs.yaml"},
                    {"name": "Private inputs", "ansible.builtin.import_tasks": "bootstrap/secrets.yaml"},
                ],
            }
        ]
        (self.root / "ansible/playbooks/test-secrets.yaml").write_text(yaml.safe_dump(play))
        result = self.run_play("test-secrets.yaml", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("SENTINEL_PRIVATE_SECRET", result.stdout + result.stderr)
        self.assertIn("censored", result.stdout)

    def test_secrets_permissions_are_enforced_before_loading(self) -> None:
        self.initialize()
        self.valid_host()
        (self.directory / "secrets.yaml").chmod(0o644)
        play = [
            {
                "name": "Test private permissions",
                "hosts": "localhost",
                "gather_facts": False,
                "tasks": [
                    {"name": "Public inputs", "ansible.builtin.import_tasks": "bootstrap/inputs.yaml"},
                    {"name": "Private inputs", "ansible.builtin.import_tasks": "bootstrap/secrets.yaml"},
                ],
            }
        ]
        (self.root / "ansible/playbooks/test-secrets.yaml").write_text(yaml.safe_dump(play))
        self.assertNotEqual(self.run_play("test-secrets.yaml", check=False).returncode, 0)

    @unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH is not installed")
    def test_native_trust_refuses_changed_authenticated_keys(self) -> None:
        self.initialize()
        keys = []
        for number in range(2):
            path = self.root / f"key-{number}"
            subprocess.run(  # noqa: S603
                [shutil.which("ssh-keygen"), "-q", "-t", "ed25519", "-N", "", "-f", str(path)],
                check=True,
                capture_output=True,
                timeout=15,
            )
            keys.append(" ".join(path.with_suffix(".pub").read_text().split()[:2]))
        play = [
            {
                "name": "Test authenticated trust",
                "hosts": "localhost",
                "gather_facts": False,
                "vars": {"bootstrap_dir": str(self.directory), "bootstrap_address": "192.0.2.10", "bootstrap_trusted_key": keys[0]},
                "tasks": [{"name": "Pin trust", "ansible.builtin.import_tasks": "bootstrap/trust.yaml"}],
            }
        ]
        source = self.root / "ansible/playbooks/test-trust.yaml"
        source.write_text(yaml.safe_dump(play))
        self.run_play("test-trust.yaml")
        before = (self.directory / "known_hosts").read_bytes()
        play[0]["vars"]["bootstrap_trusted_key"] = keys[1]
        source.write_text(yaml.safe_dump(play))
        self.assertNotEqual(self.run_play("test-trust.yaml", check=False).returncode, 0)
        self.assertEqual((self.directory / "known_hosts").read_bytes(), before)

    def test_proxmox_native_filters_bind_discovery_to_the_expected_nic(self) -> None:
        source = yaml.safe_load((ROOT / "ansible/playbooks/bootstrap/proxmox.yaml").read_text())
        names = {
            "Check guest identity before accepting it",
            "Bind discovery to the VM's primary NIC MAC",
            "Select usable IPv4 addresses only on that NIC",
            "Refuse ambiguous addressing or a different reserved address",
        }
        tasks = [task for task in source if task["name"] in names]
        interfaces = [
            {"hardware-address": "aa:bb:cc:dd:ee:00", "ip-addresses": [{"ip-address-type": "ipv4", "ip-address": "192.0.2.10"}]},
            {"hardware-address": "aa:bb:cc:dd:ee:01", "ip-addresses": [{"ip-address-type": "ipv4", "ip-address": "172.20.0.1"}]},
        ]
        play = [
            {
                "name": "Test native Proxmox JSON filters",
                "hosts": "localhost",
                "gather_facts": False,
                "vars": {
                    "bootstrap": {"name": "guest", "proxmox_username": "admin", "proxmox_vmid": 999, "proxmox_address": "auto"},
                    "bootstrap_pve_config": {
                        "stdout": json.dumps(
                            {
                                "name": "guest",
                                "ciuser": "admin",
                                "scsi0": "local-lvm:vm-999-disk-0",
                                "cicustom": "user=local:snippets/ubuntu-26.04-999-cloud-user.yaml",
                                "net0": "virtio=AA:BB:CC:DD:EE:00,bridge=vmbr0",
                            }
                        )
                    },
                    "bootstrap_pve_interfaces": {"stdout": json.dumps(interfaces)},
                },
                "tasks": tasks,
            }
        ]
        path = self.root / "ansible/playbooks/test-proxmox.yaml"
        path.write_text(yaml.safe_dump(play))
        self.run_play("test-proxmox.yaml")
        interfaces[0]["ip-addresses"].append({"ip-address-type": "ipv4", "ip-address": "192.0.2.11"})
        play[0]["vars"]["bootstrap_pve_interfaces"]["stdout"] = json.dumps(interfaces)
        path.write_text(yaml.safe_dump(play))
        self.assertNotEqual(self.run_play("test-proxmox.yaml", check=False).returncode, 0)

    def test_inspection_refuses_a_symlink_to_private_input(self) -> None:
        self.initialize()
        (self.directory / "host.yaml").unlink()
        (self.directory / "secrets.yaml").write_text("private: SENTINEL_PRIVATE_SECRET")
        (self.directory / "host.yaml").symlink_to(self.directory / "secrets.yaml")
        result = self.run_play("bootstrap-inspect.yaml", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("SENTINEL_PRIVATE_SECRET", result.stdout + result.stderr)

    def test_native_dns_policy_refuses_conflicts_without_claiming_matching_records(self) -> None:
        source = yaml.safe_load((ROOT / "ansible/playbooks/bootstrap/dns-record.yaml").read_text())
        check = next(task for task in source if task["name"].startswith("Refuse conflicting"))
        matching = {"id": "owned-id", "type": "A", "content": "192.0.2.10", "proxied": False}
        play = [
            {
                "name": "Test DNS ownership policy",
                "hosts": "localhost",
                "gather_facts": False,
                "vars": {
                    "bootstrap_dns_rows": [matching],
                    "bootstrap_address": "192.0.2.10",
                    "bootstrap_dns_provider": "cloudflare",
                    "bootstrap_dns_owned": [],
                },
                "tasks": [check],
            }
        ]
        path = self.root / "ansible/playbooks/test-dns.yaml"
        path.write_text(yaml.safe_dump(play))
        self.run_play("test-dns.yaml")
        for wrong in ({**matching, "content": "192.0.2.11"}, {**matching, "proxied": True}):
            play[0]["vars"]["bootstrap_dns_rows"] = [wrong]
            path.write_text(yaml.safe_dump(play))
            self.assertNotEqual(self.run_play("test-dns.yaml", check=False).returncode, 0)
        play[0]["vars"]["bootstrap_dns_rows"] = [matching]
        play[0]["vars"]["bootstrap_dns_owned"] = [{"id": "different-id"}]
        path.write_text(yaml.safe_dump(play))
        self.assertNotEqual(self.run_play("test-dns.yaml", check=False).returncode, 0)

    def test_dns_ownership_uses_the_native_cloudflare_result_shape(self) -> None:
        source = yaml.safe_load((ROOT / "ansible/playbooks/bootstrap/dns-record.yaml").read_text())
        track = next(task for task in source if task["name"].startswith("Track only records"))
        for provider, expected_id in (("cloudflare", "created-record-id"), ("adguard", None)):
            play = [
                {
                    "name": "Test native DNS result parsing",
                    "hosts": "localhost",
                    "gather_facts": False,
                    "vars": {
                        "bootstrap_dns_action": "present",
                        "bootstrap_dns_rows": [],
                        "bootstrap_dns_owned": [],
                        "bootstrap_dns_records": [],
                        "bootstrap_dns_provider": provider,
                        "bootstrap_dns_name": "test.example.com",
                        "bootstrap_address": "192.0.2.10",
                        "bootstrap_cf_write": {"changed": True, "result": {"record": {"id": "created-record-id"}}},
                    },
                    "tasks": [
                        track,
                        {
                            "name": "Require the created record identity",
                            "ansible.builtin.assert": {"that": "bootstrap_dns_records == expected_records"},
                            "vars": {
                                "expected_records": [{"provider": provider, "name": "test.example.com", "answer": "192.0.2.10", "id": expected_id}]
                            },
                        },
                    ],
                }
            ]
            (self.root / "ansible/playbooks/test-dns-result.yaml").write_text(yaml.safe_dump(play))
            self.run_play("test-dns-result.yaml")

    def test_dns_provider_can_be_added_but_owned_records_and_pending_writes_stay_protected(self) -> None:
        source = yaml.safe_load((ROOT / "ansible/playbooks/bootstrap/dns.yaml").read_text())
        guard = next(task for task in source if task["name"].startswith("Preserve evidence"))
        identity = {
            "target": "aws",
            "name": "guest",
            "domain": "test.example.com",
            "cloudflare_zone": "example.com",
            "adguard_url": "https://adguard.example.com",
        }
        receipt = {"identity": {**identity, "adguard_url": ""}, "records": [], "pending": None}
        play = [
            {
                "name": "Test adding a DNS provider",
                "hosts": "localhost",
                "gather_facts": False,
                "vars": {"bootstrap_dns_stat": {"stat": {"exists": True}}, "bootstrap_dns_identity": identity, "bootstrap_dns_receipt": receipt},
                "tasks": [guard],
            }
        ]
        path = self.root / "ansible/playbooks/test-dns-provider.yaml"
        path.write_text(yaml.safe_dump(play))
        self.run_play("test-dns-provider.yaml")
        receipt["identity"]["adguard_url"] = "https://original-adguard.example.com"
        receipt["records"] = [{"provider": "adguard", "name": "test.example.com", "answer": "192.0.2.10", "id": None}]
        path.write_text(yaml.safe_dump(play))
        self.assertNotEqual(self.run_play("test-dns-provider.yaml", check=False).returncode, 0)
        receipt["records"] = []
        receipt["identity"] = identity.copy()
        receipt["pending"] = {"provider": "adguard", "name": "test.example.com", "answer": "192.0.2.10"}
        path.write_text(yaml.safe_dump(play))
        self.assertNotEqual(self.run_play("test-dns-provider.yaml", check=False).returncode, 0)

    def test_tagged_teardown_executes_nested_dns_deletes_and_readback(self) -> None:
        self.directory.mkdir(parents=True)
        domain = "test.example.com"
        address = "192.0.2.10"
        records = [{"provider": "cloudflare", "name": name, "answer": address, "id": "record-" + name} for name in (domain, "*." + domain)]
        identity = {"target": "aws", "name": "guest", "domain": domain, "cloudflare_zone": "example.com", "adguard_url": ""}
        (self.directory / "dns-state.yaml").write_text(yaml.safe_dump({"identity": identity, "records": records, "pending": None}))
        dns_dir = self.root / "ansible/playbooks/bootstrap"
        tasks = yaml.safe_load((dns_dir / "dns.yaml").read_text())
        for task in tasks:
            if "ansible.builtin.uri" in task:
                del task["ansible.builtin.uri"]
                del task["register"]
                task["ansible.builtin.set_fact"] = {"bootstrap_cf_zone": {"json": {"success": True, "result": [{"id": "zone"}]}}}
        (dns_dir / "dns.yaml").write_text(yaml.safe_dump(tasks))
        (dns_dir / "dns-read.yaml").write_text(
            yaml.safe_dump(
                [
                    {
                        "name": "Read the offline provider record",
                        "ansible.builtin.set_fact": {
                            "bootstrap_dns_rows": "{{ [] if bootstrap_dns_name in test_deleted | default([]) else [{'id': 'record-' + bootstrap_dns_name, 'type': 'A', 'content': bootstrap_address, 'proxied': false}] }}"
                        },
                    }
                ]
            )
        )
        record_tasks = yaml.safe_load((dns_dir / "dns-record.yaml").read_text())
        for task in record_tasks:
            if "community.general.cloudflare_dns" in task:
                del task["community.general.cloudflare_dns"]
                task["ansible.builtin.set_fact"] = {"test_deleted": "{{ test_deleted | default([]) + [bootstrap_dns_name] }}"}
        (dns_dir / "dns-record.yaml").write_text(yaml.safe_dump(record_tasks))
        play = [
            {
                "name": "Test tagged DNS teardown",
                "hosts": "localhost",
                "gather_facts": False,
                "vars": {
                    "bootstrap": {"target": "aws", "name": "guest", "domain": domain, "dns": {"enabled": False, "cloudflare_zone": "example.com"}},
                    "bootstrap_dir": str(self.directory),
                    "bootstrap_address": address,
                    "bootstrap_dns_action": "absent",
                },
                "tasks": [
                    {"name": "Run tagged cleanup", "ansible.builtin.import_tasks": "bootstrap/dns.yaml", "tags": ["cleanup"]},
                    {
                        "name": "Require actual provider deletion",
                        "ansible.builtin.assert": {"that": ["test_deleted | default([]) | length == 2", "bootstrap_dns_records | length == 0"]},
                        "tags": ["cleanup"],
                    },
                ],
            }
        ]
        (self.root / "ansible/playbooks/test-dns-cleanup.yaml").write_text(yaml.safe_dump(play))
        self.run_play("test-dns-cleanup.yaml", tags="cleanup")
        self.assertEqual(yaml.safe_load((self.directory / "dns-state.yaml").read_text())["records"], [])

    def prepare_teardown_fixture(self) -> dict:
        self.initialize()
        host = self.valid_host()
        host["dns"] = {"enabled": False}
        (self.directory / "host.yaml").write_text(yaml.safe_dump(host))
        (self.directory / "secrets.yaml").write_text("cloudflare_token: fixture-token\n")
        handoff = {
            "name": host["name"],
            "account_id": "555555555555",
            "region": "eu-central-1",
            "instance_id": "i-fixture",
            "root_volume_id": "vol-root",
            "data_volume_id": "vol-data",
            "allocation_id": "eipalloc-fixture",
            "vpc_id": "vpc-fixture",
            "role_name": "fixture-role",
            "profile_name": "fixture-profile",
            "key_name": "fixture-key",
            "address": "192.0.2.10",
            "username": "ubuntu",
        }
        (self.directory / "teardown-host.yaml").write_text(yaml.safe_dump(handoff))
        (self.directory / "aws.tfstate").write_text("{}\n")
        (self.directory / "destroy.tfplan").write_text("fixture saved plan\n")
        (self.directory / ".terraform").mkdir()
        identity = {"target": "aws", "name": host["name"], "domain": host["domain"], "cloudflare_zone": "", "adguard_url": ""}
        (self.directory / "dns-state.yaml").write_text(yaml.safe_dump({"identity": identity, "records": [], "pending": None}))
        self.env["TEARDOWN_TEST_HANDOFF"] = json.dumps(handoff)
        self.env["TEARDOWN_TEST_LOG"] = str(self.root / "teardown-calls.log")
        stub = """import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["TEARDOWN_TEST_LOG"], "a") as log:
    log.write(name + " " + " ".join(args) + "\\n")
if name == "terraform":
    if "output" in args: print(os.environ["TEARDOWN_TEST_HANDOFF"])
    elif args[-2:] == ["state", "list"]: print(os.environ.get("TEARDOWN_TEST_STATE", ""))
    elif "apply" not in args: sys.exit(91)
elif name == "aws":
    if "get-caller-identity" in args: print(os.environ.get("TEARDOWN_TEST_ACCOUNT", "555555555555"))
    elif "get-role" in args or "get-instance-profile" in args:
        code = "AccessDenied" if os.environ.get("TEARDOWN_TEST_IAM_DENIED") else "NoSuchEntity"
        print("An error occurred (" + code + ")", file=sys.stderr)
        sys.exit(254)
    elif "describe-instances" in args and args[-1] == "json":
        state = os.environ.get("TEARDOWN_TEST_INSTANCE", "running")
        print(json.dumps([] if state == "absent" else [state]))
    elif any(arg.startswith("describe-") for arg in args):
        print("1" if os.environ.get("TEARDOWN_TEST_REMAINING", "never") in args else "0")
    else: sys.exit(91)
elif name == "docker":
    if args == ["ps", "-q"]: print("container-one\\ncontainer-two")
elif name == "systemctl": pass
elif name == "umount": sys.exit(1 if os.environ.get("TEARDOWN_TEST_UNMOUNT_FAIL") else 0)
elif name == "findmnt": sys.exit(1)
else: sys.exit(91)
"""
        for name in ("aws", "terraform", "docker", "systemctl", "umount", "findmnt"):
            executable = self.root / "bin" / name
            executable.write_text("#!/usr/bin/env python3\n" + stub)
            executable.chmod(0o700)
        verification = self.root / "ansible/playbooks/bootstrap/verify-destroyed.yaml"
        tasks = yaml.safe_load(verification.read_text())
        for task in tasks:
            if "retries" in task:
                task["retries"] = 0
                task["delay"] = 0
        verification.write_text(yaml.safe_dump(tasks))
        # Exercise shutdown ordering locally, with no real SSH, systemd or mount actions.
        shutdown = self.root / "ansible/playbooks/bootstrap-quiesce.yaml"
        plays = yaml.safe_load(shutdown.read_text())
        next(task for task in plays[0]["tasks"] if "ansible.builtin.add_host" in task)["ansible.builtin.add_host"]["ansible_connection"] = "local"
        plays[1]["become"] = False
        for task in plays[1]["tasks"][0]["block"]:
            if "ansible.builtin.service_facts" in task:
                del task["ansible.builtin.service_facts"]
                task["ansible.builtin.set_fact"] = {
                    "ansible_facts": {"services": {"docker.service": {"state": "running"}, "docker.socket": {"state": "running"}}}
                }
            elif "ansible.builtin.systemd_service" in task:
                del task["ansible.builtin.systemd_service"]
                task["ansible.builtin.command"] = {"argv": ["systemctl", "stop", "{{ item }}"]}
            elif "ansible.posix.mount" in task:
                del task["ansible.posix.mount"]
                task["ansible.builtin.command"] = {"argv": ["umount", "/storage"]}
        shutdown.write_text(yaml.safe_dump(plays))
        return handoff

    def test_teardown_verifies_exact_resources_before_removing_recovery_files(self) -> None:
        handoff = self.prepare_teardown_fixture()
        self.run_play("bootstrap-destroy.yaml", tags="cleanup")
        self.assertEqual(sorted(path.name for path in self.directory.iterdir()), ["aws.tfvars", "host.yaml", "secrets.yaml"])
        calls = (self.root / "teardown-calls.log").read_text()
        for field in ("instance_id", "root_volume_id", "data_volume_id", "allocation_id", "vpc_id", "role_name", "profile_name", "key_name"):
            self.assertIn(handoff[field], calls)
        self.assertNotIn("terraform apply", calls)

    def test_teardown_preserves_evidence_on_wrong_account_remaining_resources_or_access_errors(self) -> None:
        handoff = self.prepare_teardown_fixture()
        for key, value in (
            ("TEARDOWN_TEST_ACCOUNT", "444444444444"),
            ("TEARDOWN_TEST_REMAINING", "describe-volumes"),
            ("TEARDOWN_TEST_REMAINING", "describe-snapshots"),
            ("TEARDOWN_TEST_IAM_DENIED", "1"),
            ("TEARDOWN_TEST_STATE", "aws_ebs_volume.data"),
        ):
            with self.subTest(failure=value):
                self.env[key] = value
                self.assertNotEqual(self.run_play("bootstrap-destroy.yaml", tags="cleanup", check=False).returncode, 0)
                for name in ("aws.tfstate", "teardown-host.yaml", "dns-state.yaml", "destroy.tfplan", ".terraform"):
                    self.assertTrue((self.directory / name).exists(), name)
                del self.env[key]
        del handoff["root_volume_id"]
        (self.directory / "teardown-host.yaml").write_text(yaml.safe_dump(handoff))
        self.assertNotEqual(self.run_play("bootstrap-destroy.yaml", tags="cleanup", check=False).returncode, 0)
        self.assertTrue((self.directory / "aws.tfstate").exists())
        self.assertTrue((self.directory / "dns-state.yaml").exists())

    def test_teardown_quiesces_in_order_and_skips_nonrunning_guests(self) -> None:
        self.prepare_teardown_fixture()
        self.run_play("bootstrap-quiesce.yaml")
        log = self.root / "teardown-calls.log"
        calls = log.read_text()
        operations = [
            "docker ps -q",
            "docker stop -t 30 container-one container-two",
            "systemctl stop docker.socket",
            "systemctl stop docker.service",
            "umount /storage",
            "findmnt --mountpoint /storage",
        ]
        positions = [calls.index(operation) for operation in operations]
        self.assertEqual(positions, sorted(positions))
        for state in ("stopped", "terminated", "absent"):
            self.env["TEARDOWN_TEST_INSTANCE"] = state
            log.write_text("")
            self.run_play("bootstrap-quiesce.yaml")
            self.assertNotIn("docker ", log.read_text())
            self.assertNotIn("umount ", log.read_text())

    @unittest.skipUnless(shutil.which("task"), "Task is not installed")
    def test_failed_unmount_prevents_the_task_from_applying_destruction(self) -> None:
        self.prepare_teardown_fixture()
        shutil.copy(ROOT / "ansible/Taskfile.bootstrap.yaml", self.root / "ansible/Taskfile.bootstrap.yaml")
        (self.root / "Taskfile.yaml").write_text("version: '3'\nincludes:\n  bootstrap: ./ansible/Taskfile.bootstrap.yaml\n")
        self.env["TEARDOWN_TEST_UNMOUNT_FAIL"] = "1"
        result = subprocess.run(  # noqa: S603
            [shutil.which("task"), "--yes", "bootstrap:destroy", "TARGET=aws", "BOOTSTRAP_CONFIG_DIR=config/bootstrap"],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = (self.root / "teardown-calls.log").read_text()
        self.assertIn("umount /storage", calls)
        self.assertNotIn("terraform -chdir=" + str(self.root / "terraform/aws-vm") + " apply", calls)
        self.assertNotIn(" apply ", calls)
        self.assertTrue((self.directory / "teardown-host.yaml").exists())


class BootstrapStructureTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("task"), "Task is not installed")
    def test_root_task_passes_bootstrap_directory_without_include_collisions(self) -> None:
        with tempfile.TemporaryDirectory(dir=TEST_TEMP_ROOT if TEST_TEMP_ROOT.is_dir() else None) as temporary:
            wrapper = Path(temporary) / "ansible-playbook"
            wrapper.write_text(
                '#!/bin/sh\nprintf "BOOTSTRAP_TEST_DIR=%s\\nBOOTSTRAP_TEST_REGION=%s\\n" "$BOOTSTRAP_DIR" "${AWS_DEFAULT_REGION-__UNSET__}"\n'
            )
            wrapper.chmod(0o700)
            for target, arguments, expected in (
                ("aws", [], "config/bootstrap-aws"),
                ("proxmox", [], "config/bootstrap-proxmox"),
                ("aws", ["BOOTSTRAP_CONFIG_DIR=config/custom-test"], "config/custom-test"),
                ("proxmox", ["BOOTSTRAP_CONFIG_DIR=config/custom-test"], "config/custom-test"),
            ):
                result = subprocess.run(  # noqa: S603
                    [shutil.which("task"), "bootstrap:init", f"TARGET={target}", *arguments],
                    cwd=ROOT,
                    env={
                        **{key: value for key, value in os.environ.items() if key != "AWS_DEFAULT_REGION"},
                        "PATH": temporary + os.pathsep + os.environ["PATH"],
                    },
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"BOOTSTRAP_TEST_DIR={ROOT / expected}\n", result.stdout)
                self.assertIn("BOOTSTRAP_TEST_REGION=__UNSET__\n", result.stdout)

    @unittest.skipUnless(shutil.which("task"), "Task is not installed")
    def test_root_tasks_reject_missing_misspelled_and_invalid_target_before_commands(self) -> None:
        with tempfile.TemporaryDirectory(dir=TEST_TEMP_ROOT if TEST_TEMP_ROOT.is_dir() else None) as temporary:
            for name in ("ansible-playbook", "terraform"):
                wrapper = Path(temporary) / name
                wrapper.write_text('#!/bin/sh\nprintf "BOOTSTRAP_TEST_UNEXPECTED_COMMAND\\n"\n')
                wrapper.chmod(0o700)
            env = {key: value for key, value in os.environ.items() if key not in ("TARGET", "BOOTSTRAP_TARGET")}
            env["PATH"] = temporary + os.pathsep + env["PATH"]
            for task in ("init", "show-config", "plan", "apply", "configure", "verify", "destroy-plan", "destroy", "destroy-cleanup"):
                for arguments in ([], ["TARGER=aws"], ["TARGER=proxmox"], ["TARGET="], ["TARGET=other"]):
                    with self.subTest(task=task, arguments=arguments):
                        result = subprocess.run(  # noqa: S603
                            [shutil.which("task"), "--yes", f"bootstrap:{task}", *arguments],
                            cwd=ROOT,
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=30,
                            check=False,
                        )
                        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertIn("TARGET", result.stderr)
                        self.assertNotIn("BOOTSTRAP_TEST_UNEXPECTED_COMMAND", result.stdout)

    @unittest.skipUnless(shutil.which("terraform"), "Terraform is not installed")
    def test_native_destroy_override_and_saved_plan_work_without_cloud_resources(self) -> None:
        """Exercise the actual generated HCL with Terraform's built-in provider."""
        with tempfile.TemporaryDirectory(dir=TEST_TEMP_ROOT if TEST_TEMP_ROOT.is_dir() else None) as temporary:
            fixture = Path(temporary)
            main = 'resource "terraform_data" "data" {\n  input = "fixture"\n  lifecycle {\n    prevent_destroy = true\n  }\n}\n'
            (fixture / "main.tf").write_text(main)
            play = yaml.safe_load((ROOT / "ansible/playbooks/bootstrap-destroy-plan.yaml").read_text())
            generated = next(task["block"][0]["ansible.builtin.copy"]["content"] for task in play[0]["tasks"] if "block" in task)
            env = {key: value for key, value in os.environ.items() if not key.startswith("TF_")}
            env["CHECKPOINT_DISABLE"] = "1"

            def terraform(*arguments):
                return subprocess.run(  # noqa: S603
                    [shutil.which("terraform"), *arguments],
                    cwd=fixture,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )

            self.assertEqual(terraform("init", "-backend=false", "-input=false").returncode, 0)
            self.assertEqual(terraform("apply", "-auto-approve", "-input=false").returncode, 0)
            self.assertNotEqual(terraform("plan", "-destroy", "-input=false").returncode, 0)
            override = fixture / "bootstrap_destroy_override.tf"
            override.write_text(generated.replace("aws_ebs_volume", "terraform_data"))
            result = terraform("plan", "-destroy", "-input=false", "-out=destroy.tfplan")
            self.assertEqual(result.returncode, 0, result.stderr)
            override.unlink()
            result = terraform("apply", "-input=false", "destroy.tfplan")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(terraform("state", "list").stdout.strip(), "")
            self.assertEqual((fixture / "main.tf").read_text(), main)

    def test_native_service_modules_and_isolated_inventory(self) -> None:
        source = "\n".join(p.read_text() for p in (ROOT / "ansible/playbooks/bootstrap").glob("*.yaml"))
        self.assertNotIn("config/ansible/inventory/inventory.yaml", source)
        self.assertIn("community.general.cloudflare_dns:", source)
        self.assertIn("community.dns.adguardhome_rewrite:", source)
        self.assertIn("community.docker.docker_compose_v2:", source)

    def test_bootstrap_environment_is_scoped_to_operational_tasks(self) -> None:
        taskfile = yaml.safe_load((ROOT / "ansible/Taskfile.bootstrap.yaml").read_text())
        self.assertNotIn("env", taskfile)
        self.assertNotIn("env", taskfile["tasks"]["test"])

    def test_all_native_yaml_is_parseable(self) -> None:
        paths = list((ROOT / "ansible/playbooks/bootstrap").glob("*.yaml"))
        paths.extend((ROOT / "ansible/playbooks").glob("bootstrap*.yaml"))
        paths.append(ROOT / "ansible/Taskfile.bootstrap.yaml")
        for path in paths:
            with self.subTest(path=path.name):
                self.assertIsNotNone(yaml.safe_load(path.read_text()))
