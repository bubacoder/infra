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

from scripts.bootstrap.config import ConfigError, Configuration, main

ROOT = Path(__file__).resolve().parents[2]
TEST_TEMP_ROOT = Path("/tmp/opencode")  # noqa: S108 -- optional harness directory


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TEST_TEMP_ROOT if TEST_TEMP_ROOT.is_dir() else None)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        shutil.copytree(ROOT / "config-example", self.root / "config-example")
        shutil.copytree(ROOT / "ansible/roles", self.root / "ansible/roles")
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

    def test_k3s_init_profile_on_both_targets_is_private_and_preserves_provider_settings(self):
        for target in ("proxmox", "aws"):
            with self.subTest(target=target):
                deployment = Configuration(self.root, self.root / f"config/k3s-{target}", target)
                with patch.object(Configuration, "detect_aws") as detect:
                    deployment.init("k3s", api_host="api.example.com", context="k3s-lab")
                    self.assertEqual(detect.call_count, int(target == "aws"))
                value = deployment.load()
                template = yaml.safe_load((self.root / f"config-example/bootstrap-{target}.yaml").read_text())
                self.assertEqual(value[target], template[target])
                self.assertEqual(value["roles"], ["debian_base", "k3s"])
                self.assertEqual(value["services"], [])
                self.assertEqual(value["secrets"], {})
                self.assertEqual(value["host"], {})
                self.assertFalse(value["dns"]["enabled"])
                self.assertEqual(value["k3s"]["access"]["context"], "k3s-lab")
                self.assertEqual(value["vm"]["name"], f"k3s-{target}")
                before = deployment.source.read_bytes()
                with patch.object(Configuration, "detect_aws"):
                    deployment.init("k3s", api_host="api.example.com", context="k3s-lab")
                self.assertEqual(deployment.source.read_bytes(), before)
                with self.assertRaises(ConfigError):
                    deployment.init("docker")
                with self.assertRaises(ConfigError):
                    deployment.init("k3s", api_host="different.example.com")
                with self.assertRaises(ConfigError):
                    deployment.init("k3s", api_host="api.example.com", context="different")
                self.assertEqual(deployment.source.read_bytes(), before)
                self.assertEqual(stat.S_IMODE(deployment.source.stat().st_mode), 0o600)

    def test_k3s_init_without_access_and_invalid_profile_options(self):
        deployment = Configuration(self.root, self.root / "config/k3s", "proxmox")
        deployment.init("k3s")
        self.assertEqual(deployment.show()["k3s_access"], {"enabled": False})
        for kwargs in (
            {"profile": "bad"},
            {"profile": "docker", "api_host": "api.example.com"},
            {"profile": "k3s", "context": "lab"},
            {"profile": "k3s", "api_host": "https://invalid"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ConfigError):
                Configuration(self.root, self.root / "config/invalid-profile", "proxmox").init(**kwargs)
        before = self.config.source.read_bytes()
        with self.assertRaises(ConfigError):
            self.config.init("k3s")
        self.assertEqual(self.config.source.read_bytes(), before)

    def test_managed_dns_rejects_short_names_offline_without_generation_or_provider_access(self):
        for case in yaml.safe_load((ROOT / "tests/bootstrap/fixtures/dns-names.yaml").read_text()):
            with self.subTest(case=case):
                self.edit(lambda v, name=case["name"]: v["host"].update(domain=name))
                with patch("scripts.bootstrap.config.subprocess.run") as run:
                    if case["valid"]:
                        self.config.show()
                    else:
                        with self.assertRaisesRegex(ConfigError, "fully qualified"):
                            self.config.show()
                        with self.assertRaisesRegex(ConfigError, "fully qualified"):
                            self.config.run("plan")
                    run.assert_not_called()
                self.assertFalse(self.config.generated.exists())

    def test_proxmox_phase_timeouts_have_compatible_defaults_and_strict_bounds(self):
        self.edit(lambda v: [v["proxmox"].pop(key) for key in ("agent_timeout_seconds", "cloud_init_timeout_seconds")])
        self.config.prepare()
        host = yaml.safe_load((self.config.generated / "host.yaml").read_text())
        self.assertEqual(host["proxmox_agent_timeout_seconds"], 600)
        self.assertEqual(host["proxmox_cloud_init_timeout_seconds"], 1800)
        self.edit(lambda v: v["proxmox"].update(agent_timeout_seconds=300, cloud_init_timeout_seconds=2400))
        self.config.prepare()
        env = (self.config.generated / "ubuntu-cloud.env").read_text()
        self.assertIn("AGENT_TIMEOUT_SECONDS=300\n", env)
        self.assertIn("CLOUD_INIT_TIMEOUT_SECONDS=2400\n", env)
        for key in ("agent_timeout_seconds", "cloud_init_timeout_seconds"):
            for value in (0, -1, True, "600", 86401):
                self.edit(lambda v, field=key, timeout=value: v["proxmox"].update({field: timeout}))
                with self.subTest(key=key, value=value), self.assertRaises(ConfigError):
                    self.config.show()
            self.edit(lambda v, field=key: v["proxmox"].update({field: 600}))

    def test_failed_provision_reports_safe_recovery_commands_without_retrying(self):
        stream = io.StringIO()
        with (
            contextlib.redirect_stderr(stream),
            patch("scripts.bootstrap.config.subprocess.run", return_value=subprocess.CompletedProcess([], 1)) as run,
        ):
            self.assertEqual(self.config.run("vm-provision"), 1)
        self.assertEqual(run.call_count, 1)
        self.assertIn("Do not retry VM creation", stream.getvalue())
        self.assertIn("bootstrap:status TARGET=proxmox BOOTSTRAP_CONFIG_DIR=config/deployment", stream.getvalue())
        self.assertIn("bootstrap:vm-wait", stream.getvalue())

    def test_cloud_init_starts_agent_before_upgrade_and_propagates_errors(self):
        user_data = self.root / "cloud.yaml"
        script = 'source "$1"; get_authorized_keys() { echo "      - ssh-ed25519 fixture"; }; VMNAME=fixture; USERNAME=admin; write_ubuntu_cloud_user_data "$2"'
        subprocess.run([shutil.which("bash"), "-c", script, "test", str(ROOT / "vm/lib-common.sh"), str(user_data)], check=True)  # noqa: S603
        config = yaml.safe_load(user_data.read_text())
        self.assertFalse(config["package_upgrade"])
        self.assertIn("qemu-guest-agent", config["packages"])
        commands = config["runcmd"]
        self.assertEqual(len(commands), 1)
        binaries = self.root / "mock-bin"
        binaries.mkdir()
        trace = self.root / "trace"
        for name, code in (
            ("systemctl", 'echo agent >> "$TRACE"; exit "${AGENT_RC:-0}"'),
            ("apt-get", 'echo upgrade >> "$TRACE"; exit "${UPGRADE_RC:-0}"'),
        ):
            executable = binaries / name
            executable.write_text("#!/bin/sh\n" + code + "\n")
            executable.chmod(0o700)
        for agent_rc, upgrade_rc, expected in ((0, 0, ["agent", "upgrade"]), (1, 0, ["agent"]), (0, 1, ["agent", "upgrade"])):
            with self.subTest(agent_rc=agent_rc, upgrade_rc=upgrade_rc):
                trace.write_text("")
                env = {
                    **os.environ,
                    "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                    "TRACE": str(trace),
                    "AGENT_RC": str(agent_rc),
                    "UPGRADE_RC": str(upgrade_rc),
                }
                result = subprocess.run([shutil.which("sh"), "-c", commands[0]], env=env, check=False)  # noqa: S603 -- generated fixture, executable stubs only
                self.assertEqual(result.returncode, int(bool(agent_rc or upgrade_rc)))
                self.assertEqual(trace.read_text().splitlines(), expected)

    def test_setup_falls_back_when_harness_directory_is_absent(self):
        is_dir = Path.is_dir
        fixture = ConfigurationTests()
        try:
            with (
                patch.object(Path, "is_dir", lambda path: False if path == TEST_TEMP_ROOT else is_dir(path)),
                patch("tempfile.TemporaryDirectory", wraps=tempfile.TemporaryDirectory) as temporary,
            ):
                fixture.setUp()
                self.assertIsNone(temporary.call_args.kwargs["dir"])
        finally:
            fixture.doCleanups()

    def test_repository_aliases_dispatch_with_a_canonical_directory(self):
        for parent_alias in (False, True):
            with self.subTest(parent_alias=parent_alias):
                alias = self.root.parent / (self.root.name + ("-parent-alias" if parent_alias else "-alias"))
                alias.symlink_to(self.root.parent if parent_alias else self.root, target_is_directory=True)
                self.addCleanup(alias.unlink)
                repository = alias / self.root.name if parent_alias else alias
                config = Configuration(self.root, repository / "config/deployment", "proxmox")
                with patch("scripts.bootstrap.config.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run:
                    self.assertEqual(config.run("vm-wait"), 0)
                self.assertEqual(config.directory, self.directory)
                self.assertIn("BOOTSTRAP_CONFIG_DIR=config/deployment", run.call_args.args[0])

    def test_aliases_below_config_are_refused_even_when_they_point_to_the_repository(self):
        alias = self.root / "config/repository-alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ConfigError):
            Configuration(self.root, alias / "config/deployment", "proxmox")

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

    def test_roles_and_services_are_explicit_ordered_and_available(self):
        original = self.config.source.read_text()
        for fields in (
            {"roles": "debian_base"},
            {"roles": ["debian_base", "debian_base"]},
            {"roles": ["../debian_base"]},
            {"roles": ["missing_role"]},
            {"roles": ["debian_base"]},
            {"services": ["dashboard/homepage"]},
            {"services": ["unknown/service"]},
            {"services": ["security/traefik", "security/traefik"]},
        ):
            self.config.source.write_text(original)
            self.edit(lambda v, update=fields: v.update(update))
            with self.assertRaises(ConfigError):
                self.config.prepare()
        self.config.source.write_text(original)
        self.edit(lambda v: v.update(roles=["debian_tools", "debian_base", "debian_docker_host"]))
        self.config.prepare()
        host = yaml.safe_load((self.config.generated / "host.yaml").read_text())
        self.assertEqual(host["roles"], ["debian_tools", "debian_base", "debian_docker_host"])

    def test_host_only_needs_no_docker_tls_repository_or_dns_credentials(self):
        self.edit(lambda v: v.update(roles=["debian_base"], services=[], host={}, dns={"enabled": False}, secrets={}))
        self.config.prepare()
        host = yaml.safe_load((self.config.generated / "host.yaml").read_text())
        self.assertNotIn("docker_volumes", host)
        self.assertNotIn("domain", host)
        self.assertEqual(host["services"], [])
        self.assertEqual(yaml.safe_load((self.config.generated / "secrets.yaml").read_text()), {})
        self.assertEqual(self.config.show()["roles"], ["debian_base"])
        self.assertIsNone(self.config.show()["domain"])

    def test_future_local_role_does_not_require_compiler_changes(self):
        self.edit(lambda v: v.update(roles=["debian_base", "future_role"], services=[], host={}, dns={"enabled": False}, secrets={}))
        with self.assertRaises(ConfigError):
            self.config.prepare()
        tasks = self.root / "ansible/roles/future_role/tasks"
        tasks.mkdir(parents=True)
        (tasks / "main.yml").write_text("[]\n")
        self.config.prepare()
        self.assertEqual(self.config.show()["roles"], ["debian_base", "future_role"])

    @patch("scripts.bootstrap.config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
    def test_k3s_bootstrap_on_both_targets_uses_no_service_credentials(self, _key):
        for target in ("proxmox", "aws"):
            with self.subTest(target=target):
                if target == "aws":
                    self.aws()
                self.edit(lambda v: v.update(roles=["debian_base", "k3s"], services=[], host={}, dns={"enabled": False}, secrets={}))
                self.config.prepare()
                host = yaml.safe_load((self.config.generated / "host.yaml").read_text())
                self.assertEqual(host["roles"], ["debian_base", "k3s"])
                self.assertEqual(host["target"], target)
                self.assertEqual(host["services"], [])
                self.assertEqual(yaml.safe_load((self.config.generated / "secrets.yaml").read_text()), {})

    def test_k3s_rejects_bootstrap_docker_ingress_before_provider_access(self):
        self.edit(lambda v: v["roles"].append("k3s"))
        with self.assertRaisesRegex(ConfigError, "services"):
            self.config.prepare()

    def test_k3s_api_access_is_optional_and_resolves_dns_host(self):
        self.edit(
            lambda v: v.update(
                roles=["debian_base", "k3s"],
                services=[],
                host={"domain": "k3s.example.com"},
                dns={"enabled": True},
                secrets={},
                k3s={"access": {"enabled": True, "context": "k3s-lab", "install_context": True}},
            )
        )
        self.config.prepare()
        host = yaml.safe_load((self.config.generated / "host.yaml").read_text())
        self.assertEqual(host["k3s"]["access"]["host"], "k3s.example.com")
        self.assertEqual(self.config.show()["k3s_access"]["context"], "k3s-lab")

    @patch("scripts.bootstrap.config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
    def test_aws_api_access_is_explicit_and_does_not_put_credentials_in_terraform(self, _key):
        self.aws()
        self.edit(
            lambda v: v.update(
                roles=["k3s"],
                services=[],
                host={},
                dns={"enabled": False},
                secrets={},
                k3s={"access": {"enabled": True, "host": "198.51.100.10", "context": "k3s-aws", "install_context": True}},
            )
        )
        self.config.prepare()
        variables = json.loads((self.config.generated / "aws.tfvars.json").read_text())
        self.assertTrue(variables["k3s_api_access"])
        self.assertNotIn("k3s", variables)
        self.assertNotIn("context", variables)

    def test_k3s_access_refuses_unselected_role_implicit_admin_export_and_unsafe_endpoints(self):
        original = self.config.source.read_text()
        for overrides in (
            {"roles": ["debian_base"]},
            {"install_context": False},
            {"host": "bad host"},
            {"host": "../bad"},
            {"host": "999.999.999.999"},
            {"context": "bad/context"},
            {"enabled": "true"},
        ):
            with self.subTest(overrides=overrides):
                self.config.source.write_text(original)
                self.edit(
                    lambda v, changes=overrides: v.update(
                        roles=changes.get("roles", ["k3s"]),
                        services=[],
                        host={},
                        dns={"enabled": False},
                        secrets={},
                        k3s={
                            "access": {
                                **{"enabled": True, "host": "k3s.example.com", "context": "k3s-lab", "install_context": True},
                                **{k: x for k, x in changes.items() if k != "roles"},
                            }
                        },
                    )
                )
                with self.assertRaises(ConfigError):
                    self.config.prepare()
        self.config.source.write_text(original)

    def test_docker_role_without_services_requires_only_volume_setting(self):
        self.edit(lambda v: v.update(services=[], host={}, dns={"enabled": False}, secrets={}))
        with self.assertRaises(ConfigError):
            self.config.prepare()
        self.edit(lambda v: v["host"].update(docker_volumes="/srv/docker-volumes"))
        self.config.prepare()

    @patch("scripts.bootstrap.config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
    def test_aws_host_only_keeps_storage_inputs_without_service_credentials(self, _key):
        self.aws()
        self.edit(lambda v: v.update(roles=["debian_base"], services=[], host={}, dns={"enabled": False}, secrets={}))
        self.config.prepare()
        variables = json.loads((self.config.generated / "aws.tfvars.json").read_text())
        self.assertEqual(variables["data_disk_size_gb"], 30)
        self.assertEqual(variables["bootstrap_mode"], "external")
        self.assertNotIn("roles", variables)
        self.edit(lambda v: v.update(host={"domain": "test.example.com"}, dns={"enabled": True, "cloudflare_zone": "example.com"}))
        with self.assertRaises(ConfigError):
            self.config.prepare()

    def test_adguard_dns_without_services_needs_only_adguard_credentials(self):
        self.edit(
            lambda v: v.update(
                roles=["debian_base"],
                services=[],
                host={"domain": "test.example.com"},
                dns={"enabled": True, "adguard_urls": ["https://dns.example.com"]},
                secrets={},
            )
        )
        with self.assertRaises(ConfigError):
            self.config.prepare()
        self.edit(lambda v: v["secrets"].update(adguard_username="fixture", adguard_password="SENTINEL_PRIVATE"))
        self.config.prepare()

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

    @patch("scripts.bootstrap.config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
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

    @patch("scripts.bootstrap.config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
    def test_saved_plan_binds_all_inputs_and_plan_bytes(self, _key):
        self.aws()
        plan = self.directory / "aws.tfplan"

        def native(command, **_kwargs):
            if "ACTION=plan" in command:
                plan.write_bytes(b"PLAN")
            return subprocess.CompletedProcess(command, 0)

        with patch("scripts.bootstrap.config.subprocess.run", side_effect=native) as run:
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

    @patch("scripts.bootstrap.config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
    def test_failed_plan_invalidates_previous_receipt(self, _key):
        self.aws()
        receipt = self.directory / "apply-inputs.json"
        receipt.write_text("old")
        with patch("scripts.bootstrap.config.subprocess.run", return_value=subprocess.CompletedProcess([], 1)):
            self.assertEqual(self.config.run("plan"), 1)
        self.assertFalse(receipt.exists())

    @patch("scripts.bootstrap.config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
    def test_native_dispatch_creates_private_artifacts_and_restores_umask(self, _key):
        self.aws()
        previous = os.umask(0o022)
        try:
            for action, filename in (("plan", "aws.tfplan"), ("destroy-plan", "destroy.tfplan")):
                with self.subTest(action=action):
                    artifact = self.directory / filename

                    def native(command, artifact=artifact, **_kwargs):
                        artifact.write_bytes(b"PLAN")
                        return subprocess.CompletedProcess(command, 0)

                    with patch("scripts.bootstrap.config.subprocess.run", side_effect=native):
                        self.assertEqual(self.config.run(action), 0)
                    self.assertEqual(stat.S_IMODE(artifact.stat().st_mode), 0o600)
                    self.assertEqual(os.umask(0o022), 0o022)
            with (
                patch("scripts.bootstrap.config.subprocess.run", side_effect=OSError("simulated native failure")),
                self.assertRaises(OSError),
            ):
                self.config.run("plan")
            self.assertEqual(os.umask(0o022), 0o022)
        finally:
            os.umask(previous)

    @patch("scripts.bootstrap.config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
    def test_aws_detection_preserves_operator_edits_and_retries_safely(self, _key):
        self.aws()
        self.edit(lambda v: v["secrets"].update(cloudflare_token="123456789012-203.0.113.10/32-SENTINEL_PRIVATE"))

        def detection(command, **_kwargs):
            return subprocess.CompletedProcess(command, 0, "555555555555\n" if command[0].endswith("aws") else "8.8.8.8\n", "")

        with (
            patch("scripts.bootstrap.config.executable", side_effect=lambda name: "/mock/" + name),
            patch("scripts.bootstrap.config.subprocess.run", side_effect=detection) as run,
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
            patch.dict(os.environ, {"VMID": "99999", "PROXMOX_HOST": "wrong-host", "AGENT_TIMEOUT_SECONDS": "1", "CLOUD_INIT_TIMEOUT_SECONDS": "1"}),
            patch("scripts.bootstrap.config.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run,
        ):
            self.config.run("vm-wait")
        env = run.call_args.kwargs["env"]
        self.assertNotIn("VMID", env)
        self.assertNotIn("PROXMOX_HOST", env)
        self.assertNotIn("AGENT_TIMEOUT_SECONDS", env)
        self.assertNotIn("CLOUD_INIT_TIMEOUT_SECONDS", env)
        self.assertEqual(env["BOOTSTRAP_INPUT_DIR"], str(self.config.generated))

    @patch("scripts.bootstrap.config.public_key", return_value="ssh-ed25519 PUBLIC_FIXTURE")
    def test_destroy_plan_also_requires_matching_inputs(self, _key):
        self.aws()
        plan = self.directory / "destroy.tfplan"

        def native(command, **_kwargs):
            plan.write_bytes(b"DESTROY")
            return subprocess.CompletedProcess(command, 0)

        with patch("scripts.bootstrap.config.subprocess.run", side_effect=native) as run:
            self.config.run("destroy-plan")
            self.config.run("destroy")
            self.edit(lambda v: v["secrets"].update(cloudflare_token="SENTINEL_PRIVATE_CHANGED"))
            with self.assertRaises(ConfigError):
                self.config.run("destroy")
            self.assertEqual(run.call_count, 2)

    def test_proxmox_destroy_uses_reviewed_plan_and_rejects_changed_inputs(self):
        plan = self.directory / "proxmox-destroy-plan.json"

        def native(command, **_kwargs):
            if "ACTION=destroy-plan" in command:
                plan.write_bytes(b"REVIEWED")
            return subprocess.CompletedProcess(command, 0)

        with patch("scripts.bootstrap.config.subprocess.run", side_effect=native) as run:
            self.assertEqual(self.config.run("destroy-plan"), 0)
            self.assertEqual(stat.S_IMODE((self.directory / "destroy-inputs.json").stat().st_mode), 0o600)
            self.assertEqual(self.config.run("destroy"), 0)
            self.assertEqual(self.config.run("destroy-cleanup"), 0)
            plan.write_bytes(b"CHANGED")
            with self.assertRaisesRegex(ConfigError, "changed since review"):
                self.config.run("destroy")
            self.assertEqual(run.call_count, 3)

    def test_failed_proxmox_destroy_plan_invalidates_previous_approval(self):
        receipt = self.directory / "destroy-inputs.json"
        receipt.write_text("old")
        with patch("scripts.bootstrap.config.subprocess.run", return_value=subprocess.CompletedProcess([], 1)):
            self.assertEqual(self.config.run("destroy-plan"), 1)
        self.assertFalse(receipt.exists())

    def test_destroy_cleanup_uses_owned_context_receipt_even_if_access_disabled(self):
        plan = self.directory / "proxmox-destroy-plan.json"

        def native(command, **_kwargs):
            if "ACTION=destroy-plan" in command:
                plan.write_bytes(b"REVIEWED")
            return subprocess.CompletedProcess(command, 0)

        with patch("scripts.bootstrap.config.subprocess.run", side_effect=native):
            self.config.run("destroy-plan")
            receipt = self.directory / "k3s-access-receipt.json"
            receipt.write_text(json.dumps({"directory": str(self.directory), "context": "k3s-old", "node": self.config.load()["vm"]["name"]}))
            receipt.chmod(0o600)
            with patch("scripts.bootstrap.access.remove") as remove:
                self.config.run("destroy-cleanup")
                remove.assert_called_once_with(self.directory, "k3s-old", self.config.load()["vm"]["name"], Path.home())

    def test_cli_parse_errors_never_echo_private_values(self):
        self.config.source.write_text("secrets: [SENTINEL_PRIVATE\n")
        with (
            patch.dict(os.environ, {"BOOTSTRAP_TARGET": "proxmox", "BOOTSTRAP_DIR": str(self.directory)}),
            patch("scripts.bootstrap.config.ROOT", self.root),
            patch("sys.argv", ["config.py", "show-config"]),
        ):
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                self.assertEqual(main(), 1)
            self.assertNotIn("SENTINEL_PRIVATE", output.getvalue())

    @unittest.skipUnless(shutil.which("task"), "Task is not installed")
    def test_task_initialization_and_helper_prepare_before_native_dotenv(self):
        shutil.copytree(ROOT / "scripts", self.root / "scripts")
        (self.root / "ansible").mkdir(exist_ok=True)
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
