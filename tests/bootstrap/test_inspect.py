"""Offline, fail-closed inspection of private bootstrap configuration."""

# ruff: noqa: PT009, PT027

import contextlib
import io
import tempfile
import traceback
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from scripts.bootstrap import __main__ as cli
from scripts.bootstrap import inspect_config
from scripts.bootstrap.core import ConfigError


class InspectConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "config").mkdir()
        self.path = self.root / "config/bootstrap.yaml"

    def write(self, value) -> None:
        self.path.write_text(yaml.safe_dump(value))
        self.path.chmod(0o600)

    def show(self) -> str:
        with contextlib.redirect_stdout(io.StringIO()) as output:
            inspect_config.show(self.path, self.root)
        return output.getvalue()

    def test_both_examples_work_without_credentials_keys_or_validation(self) -> None:
        for name in ("bootstrap.yaml", "bootstrap-aws.yaml"):
            example = Path(__file__).resolve().parents[2] / "config-example" / name
            self.path.write_text(example.read_text())
            self.path.chmod(0o600)
            result = yaml.safe_load(self.show())
            self.assertEqual(result["tls"]["token"], "<redacted>")
            self.assertIn("ssh_public_key", result["vm"])

    def test_known_secrets_unknown_fields_and_nested_values_never_leak(self) -> None:
        self.write(
            {
                "version": 2,
                "target": "aws",
                "tls": {"token": "test-private-token", "new_secret": "unknown-private-value"},
                "network": {
                    "domain": "test-private-token.example.com",
                    "dns": {
                        "adguard": {
                            "url": "https://dns.example.com",
                            "username": "operator",
                            "password": "test-private-password",
                        }
                    },
                },
                "vm": {"name": {"password": "nested-private-value"}, "ssh_private_key": "private-key-material"},
                "deployment": {"services": [{"password": "nested-service-secret"}]},
                "unrecognized-private-key": "unrecognized-private-value",
            }
        )
        output = self.show()
        for value in (
            "test-private-token",
            "test-private-password",
            "unknown-private-value",
            "nested-private-value",
            "private-key-material",
            "nested-service-secret",
            "unrecognized-private",
        ):
            self.assertNotIn(value, output)
        result = yaml.safe_load(output)
        self.assertEqual(result["network"]["dns"]["adguard"]["password"], "<redacted>")
        self.assertEqual(result["network"]["dns"]["adguard"]["username"], "operator")

    def test_embedded_url_credentials_and_parameters_are_not_shown(self) -> None:
        for url in (
            "https://token-private@example.com/repo",
            "https://user:password-private@example.com/repo",
            "https://example.com/repo?token=query-private",
            "https://example.com/repo#fragment-private",
        ):
            with self.subTest(url=url):
                self.write({"repository": {"url": url}, "network": {"dns": {"adguard": {"url": url}}}})
                output = self.show()
                self.assertNotIn(url, output)
                self.assertNotIn("-private", output)

    def test_incomplete_file_is_shown_without_full_schema_validation(self) -> None:
        self.write({"target": "aws", "aws": {"region": "eu-central-1"}})
        self.assertEqual(yaml.safe_load(self.show()), {"target": "aws", "aws": {"region": "eu-central-1"}})

    def test_dns_enabled_setting_is_visible(self) -> None:
        self.write({"network": {"dns": {"enabled": False}}})
        self.assertIs(yaml.safe_load(self.show())["network"]["dns"]["enabled"], False)

    def test_syntax_errors_do_not_echo_private_content(self) -> None:
        self.path.write_text('tls:\n  token: ["never-print-private-token"\n')
        self.path.chmod(0o600)
        with self.assertRaises(ConfigError) as caught:
            self.show()
        self.assertNotIn("never-print-private-token", str(caught.exception))
        self.assertNotIn("never-print-private-token", "".join(traceback.format_exception(caught.exception)))

    def test_file_security_is_still_enforced(self) -> None:
        self.write({"tls": {"token": "not-shared"}})
        self.path.chmod(0o644)
        with self.assertRaises(ConfigError):
            self.show()
        with self.assertRaises(ConfigError):
            inspect_config.show(self.root / "elsewhere.yaml", self.root)

    def test_recursive_yaml_does_not_echo_or_recurse_forever(self) -> None:
        self.path.write_text("vm: &loop\n  name: *loop\ntls:\n  token: example-private-token\n")
        self.path.chmod(0o600)
        self.assertNotIn("example-private-token", self.show())

    def test_inspection_does_not_call_commands_network_or_change_files(self) -> None:
        self.write({"tls": {"token": "local-fixture-token"}, "aws": {"region": "eu-central-1"}})
        original = self.path.read_bytes()
        original_mode = self.path.stat().st_mode
        with (
            patch("subprocess.run", side_effect=AssertionError("No commands permitted")),
            patch("socket.create_connection", side_effect=AssertionError("No network permitted")),
            patch("socket.getaddrinfo", side_effect=AssertionError("No DNS permitted")),
        ):
            self.show()
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.path.stat().st_mode, original_mode)
        self.assertEqual(list((self.root / "config").iterdir()), [self.path])

    def test_invalid_root_and_encoding_errors_are_safe(self) -> None:
        for content in (b"- private-root-value\n", b"tls: {token: \xffprivate-encoding-value}\n"):
            self.path.write_bytes(content)
            self.path.chmod(0o600)
            with self.subTest(content=content), self.assertRaises(ConfigError) as caught:
                self.show()
            self.assertNotIn("private-", str(caught.exception))

    def test_show_config_argument_is_exclusive(self) -> None:
        with patch("sys.argv", ["bootstrap", "--show-config"]):
            self.assertTrue(cli.parse_args().show_config)
        with (
            patch("sys.argv", ["bootstrap", "--show-config", "--apply"]),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            cli.parse_args()

    def test_cli_does_not_validate_deploy_contact_services_or_write(self) -> None:
        args = SimpleNamespace(config=self.path, show_config=True, yes=False, apply=False, destroy=False, delete_data=False, dry_run=False)
        with (
            patch.object(cli, "parse_args", return_value=args),
            patch.object(cli.inspect_config, "show") as show,
            patch.object(cli.config, "load_config") as load,
            patch.object(cli.aws, "resolve_plan") as aws,
            patch.object(cli.proxmox, "resolve_plan") as proxmox,
        ):
            cli.main()
        show.assert_called_once_with(self.path)
        for mock in (load, aws, proxmox):
            mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
