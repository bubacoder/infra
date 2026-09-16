"""Unit tests for the homelab bootstrap orchestrator."""

# ruff: noqa: PT009, PT027

import contextlib
import importlib.util
import io
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

MODULE_PATH = Path(__file__).with_name("bootstrap.py")
SPEC = importlib.util.spec_from_file_location("bootstrap_script", MODULE_PATH)
bootstrap = importlib.util.module_from_spec(SPEC)
if SPEC.loader is None:
    raise RuntimeError("Cannot load bootstrap.py")
SPEC.loader.exec_module(bootstrap)


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "config").mkdir()
        examples = self.root / "config-example/ansible/inventory"
        examples.mkdir(parents=True)
        (examples / "inventory.yaml").write_text("debian:\n  hosts: {}\ndocker_hosts:\n  hosts: {}\ndebian_tools_hosts:\n  hosts: {}\n")
        self.public_key = self.root / "id_ed25519.pub"
        self.public_key.write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest bootstrap@test\n")
        self.config_path = self.root / "config/bootstrap.yaml"
        self.write_config()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def document(self) -> dict:
        return {
            "version": 1,
            "deployment": {
                "admin_model": "separate",
                "services": ["security/traefik", "dashboard/homepage"],
            },
            "proxmox": {"ssh_target": "user@proxmox"},
            "vm": {
                "id": 400,
                "name": "docker-host",
                "ubuntu_version": "26.04",
                "username": "admin",
                "cpu_cores": 4,
                "memory_max_mib": 4096,
                "memory_min_mib": 1024,
                "disk_size": "256G",
                "storage": "local-lvm",
                "bridge": "vmbr0",
                "ssh_public_key": str(self.public_key),
            },
            "network": {
                "expected_ipv4": "192.0.2.10",
                "domain": "homelab.example.com",
                "dns": {"mode": "external", "verify": True},
            },
            "host": {"docker_volumes": "/srv/docker-volumes", "timezone": "Etc/UTC"},
            "tls": {"provider": "cloudflare", "acme_email": "admin@example.com", "token": "test_token-value"},
        }

    def write_config(self, document: dict | None = None, mode: int = 0o600) -> None:
        self.config_path.write_text(yaml.safe_dump(document or self.document(), sort_keys=False))
        self.config_path.chmod(mode)

    def load(self) -> bootstrap.BootstrapConfig:
        return bootstrap.load_config(self.config_path, self.root)

    def plan(self, config: bootstrap.BootstrapConfig | None = None) -> bootstrap.BootstrapPlan:
        loaded = config or self.load()
        return bootstrap.BootstrapPlan(
            config=loaded,
            repository=self.repository(),
            vm_id=400,
            mac=loaded.vm.mac or bootstrap.generated_mac(loaded.proxmox.ssh_target, loaded.vm.name),
            vm_exists=False,
        )

    @staticmethod
    def repository() -> bootstrap.RepositoryConfig:
        return bootstrap.RepositoryConfig(
            url="https://example.com/infra.git",
            branch="bootstrap",
            commit="a" * 40,
        )

    def test_loads_supported_configuration(self) -> None:
        config = self.load()
        self.assertEqual(config.vm.name, "docker-host")
        self.assertEqual(config.deployment.services, bootstrap.SUPPORTED_SERVICES)
        self.assertEqual(config.tls.token, "test_token-value")

    def test_rejects_insecure_configuration_permissions(self) -> None:
        self.config_path.chmod(0o644)
        with self.assertRaisesRegex(bootstrap.ConfigError, "chmod 600"):
            self.load()

    def test_rejects_unknown_fields(self) -> None:
        document = self.document()
        document["vm"]["unsupported"] = True
        self.write_config(document)
        with self.assertRaisesRegex(bootstrap.ConfigError, "unknown fields"):
            self.load()

    def test_malformed_yaml_error_does_not_include_source_content(self) -> None:
        self.config_path.write_text("tls:\n  token: secret-token\n  invalid: [\n")
        self.config_path.chmod(0o600)
        with self.assertRaises(bootstrap.ConfigError) as raised:
            self.load()
        self.assertNotIn("secret-token", str(raised.exception))
        self.assertIn("Cannot parse bootstrap configuration", str(raised.exception))

    def test_rejects_repository_url_credentials(self) -> None:
        document = self.document()
        document["repository"] = {"url": "https://token@example.com/infra.git", "branch": "bootstrap"}
        self.write_config(document)
        with self.assertRaisesRegex(bootstrap.ConfigError, "must not contain credentials"):
            self.load()

    def test_rejects_ssh_repository_url_password(self) -> None:
        document = self.document()
        document["repository"] = {"url": "ssh://user:password@example.com/infra.git", "branch": "bootstrap"}
        self.write_config(document)
        with self.assertRaisesRegex(bootstrap.ConfigError, "must not contain credentials"):
            self.load()

    def test_rejects_credentials_in_detected_origin(self) -> None:
        runner = Mock()
        runner.run.side_effect = ["", "bootstrap", "https://user:secret@example.com/infra.git"]
        with self.assertRaisesRegex(bootstrap.ConfigError, "must not contain credentials"):
            bootstrap.detect_repository(self.load(), runner, self.root)

    def test_rejects_unsupported_service_set(self) -> None:
        document = self.document()
        document["deployment"]["services"].append("security/authentik")
        self.write_config(document)
        with self.assertRaisesRegex(bootstrap.ConfigError, "currently must be"):
            self.load()

    def test_generated_mac_is_stable_local_and_unicast(self) -> None:
        first = bootstrap.generated_mac("user@proxmox", "docker-host")
        second = bootstrap.generated_mac("user@proxmox", "docker-host")
        self.assertEqual(first, second)
        self.assertEqual(first[:2], "02")
        self.assertEqual(int(first[:2], 16) & 1, 0)

    def test_plan_redacts_token(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bootstrap.print_plan(self.plan())
        self.assertNotIn("test_token-value", output.getvalue())
        self.assertIn("<redacted>", output.getvalue())

    def test_render_writes_exact_managed_configuration(self) -> None:
        private_key = self.public_key.with_suffix("")
        private_key.write_text("not-a-real-private-key")
        private_key.chmod(0o600)
        plan = self.plan()
        bootstrap.render_config(plan, self.root)

        vm_env = (self.root / "config/vm/proxmox/ubuntu-cloud.env").read_text()
        self.assertIn(f"VM_MAC={plan.mac}", vm_env)
        self.assertIn("EXPECTED_IPV4=192.0.2.10", vm_env)

        inventory = yaml.safe_load((self.root / "config/ansible/inventory/inventory.yaml").read_text())
        host = inventory["debian"]["hosts"]["docker-host"]
        self.assertEqual(host["ansible_host"], "192.0.2.10")
        self.assertEqual(host["ansible_ssh_private_key_file"], str(private_key))
        self.assertIn("docker-host", inventory["docker_hosts"]["hosts"])

        host_dir = self.root / "config/docker/docker-host"
        self.assertIn("MYDOMAIN=homelab.example.com", (host_dir / ".env").read_text())
        self.assertIn("CLOUDFLARE_DNS_API_TOKEN=test_token-value", (host_dir / ".env.traefik").read_text())
        self.assertEqual(os.stat(host_dir / ".env.traefik").st_mode & 0o777, 0o600)
        services = yaml.safe_load((host_dir / "services.yaml").read_text())
        self.assertEqual(services["services"][0]["security"][0]["name"], "traefik")

    def test_dns_checkpoint_accepts_only_expected_address(self) -> None:
        expected = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.10", 0))]
        with patch.object(bootstrap.socket, "getaddrinfo", return_value=expected) as resolver:
            bootstrap.verify_dns(self.plan(), "192.0.2.10")
        names = {call.args[0] for call in resolver.call_args_list}
        self.assertIn("home.homelab.example.com", names)
        self.assertNotIn("homepage.homelab.example.com", names)

    def test_dns_checkpoint_reports_failed_names_without_secrets(self) -> None:
        with (
            patch.object(bootstrap.socket, "getaddrinfo", side_effect=socket.gaierror),
            self.assertRaisesRegex(bootstrap.BootstrapError, "External DHCP/DNS checkpoint") as raised,
        ):
            bootstrap.verify_dns(self.plan(), "192.0.2.10")
        self.assertNotIn("test_token-value", str(raised.exception))

    def test_preflight_reads_storage_from_proxmox_api(self) -> None:
        plan = self.plan()

        class StubRunner:
            def __init__(self) -> None:
                self.commands: list[list[str]] = []

            def run(self, command: list[str], **_: object) -> str:
                self.commands.append(command)
                if "pvesh get /storage/local" in command[-1]:
                    return '{"content":"iso,snippets"}'
                if "grep -Riq" in command[-1]:
                    return "available"
                return ""

        runner = StubRunner()
        with patch.object(bootstrap, "verify_dns"):
            bootstrap.preflight(plan, runner)
        self.assertTrue(any("pvesh get /storage/local" in command[-1] for command in runner.commands))

    def test_accepts_auto_ipv4_discovery(self) -> None:
        document = self.document()
        document["network"]["expected_ipv4"] = "auto"
        self.write_config(document)
        self.assertIsNone(self.load().network.expected_ipv4)

    def test_discovers_only_address_on_planned_interface(self) -> None:
        plan = self.plan()

        class StubRunner:
            def run(self, _: list[str], **__: object) -> str:
                return """[
                  {"hardware-address": "02:00:00:00:00:01", "ip-addresses": [{"ip-address-type": "ipv4", "ip-address": "192.0.2.11"}]},
                  {"hardware-address": "%s", "ip-addresses": [{"ip-address-type": "ipv4", "ip-address": "192.0.2.10"}]}
                ]""" % plan.mac

        self.assertEqual(bootstrap.discover_vm_ipv4(plan, StubRunner()), "192.0.2.10")

    def test_rejects_ambiguous_discovered_addresses(self) -> None:
        plan = self.plan()

        class StubRunner:
            def run(self, _: list[str], **__: object) -> str:
                return """[{"hardware-address": "%s", "ip-addresses": [
                  {"ip-address-type": "ipv4", "ip-address": "192.0.2.10"},
                  {"ip-address-type": "ipv4", "ip-address": "192.0.2.11"}
                ]}]""" % plan.mac

        with self.assertRaisesRegex(bootstrap.BootstrapError, "exactly one usable IPv4"):
            bootstrap.discover_vm_ipv4(plan, StubRunner())

    def test_partial_existing_vm_is_not_resumed(self) -> None:
        plan = bootstrap.BootstrapPlan(
            config=self.load(),
            repository=self.repository(),
            vm_id=400,
            mac="02:00:00:00:00:04",
            vm_exists=True,
        )

        class StubRunner:
            def run(self, command: list[str], **_: object) -> str:
                return "name: docker-host\nnet0: virtio=02:00:00:00:00:04,bridge=vmbr0\n"

        with self.assertRaisesRegex(bootstrap.BootstrapError, "incomplete"):
            bootstrap.verify_existing_vm(plan, StubRunner())


if __name__ == "__main__":
    unittest.main()
