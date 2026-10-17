"""Offline DNS reconciliation tests; no provider or resolver access."""

# ruff: noqa: PT009, PT027

import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.bootstrap import __main__ as cli
from scripts.bootstrap import config, dns, network
from scripts.bootstrap.core import AdguardDnsConfig, BootstrapError, CloudflareDnsConfig, ConfigError, DnsConfig, NetworkConfig, TlsConfig


class DnsTests(unittest.TestCase):
    def settings(self, *, cloudflare=True, adguard=True):
        settings = DnsConfig(
            "managed",
            True,
            CloudflareDnsConfig("example.com") if cloudflare else None,
            AdguardDnsConfig("https://dns.example.com", "operator", "private-password") if adguard else None,
        )
        return SimpleNamespace(
            target="aws" if cloudflare else "proxmox",
            vm=SimpleNamespace(name="test-host"),
            network=NetworkConfig("192.0.2.1", "test.example.com", settings),
            tls=TlsConfig("cloudflare", "operator@example.com", "private-token"),
        )

    def test_cloudflare_conflicts_fail_closed(self) -> None:
        for record in (
            {"type": "A", "content": "192.0.2.2", "proxied": False},
            {"type": "A", "content": "192.0.2.1", "proxied": True},
            {"type": "AAAA", "content": "2001:db8::1"},
            {"type": "CNAME", "content": "other.example.com"},
            {"type": "NS", "content": "ns.example.com"},
        ):
            with self.subTest(record=record), self.assertRaises(BootstrapError):
                dns.cloudflare_action("test.example.com", "192.0.2.1", [record])

    def test_cloudflare_same_record_is_noop_and_missing_is_create(self) -> None:
        same = {"type": "A", "content": "192.0.2.1", "proxied": False}
        self.assertFalse(dns.cloudflare_action("test.example.com", "192.0.2.1", [same]))
        self.assertTrue(dns.cloudflare_action("test.example.com", "192.0.2.1", []))
        with self.assertRaises(BootstrapError):
            dns.cloudflare_action("test.example.com", "192.0.2.1", [same, same])

    def test_adguard_exact_rewrites_preserve_broader_wildcard(self) -> None:
        records = [{"domain": "*.example.com", "answer": "192.0.2.99"}]
        self.assertTrue(dns.adguard_action("test.example.com", "192.0.2.1", records))
        records.append({"domain": "test.example.com", "answer": "192.0.2.1"})
        self.assertFalse(dns.adguard_action("test.example.com", "192.0.2.1", records))

    def test_adguard_conflicting_or_disabled_exact_rewrites_stop(self) -> None:
        for record in (
            {"domain": "test.example.com", "answer": "192.0.2.99"},
            {"domain": "test.example.com", "answer": "192.0.2.1", "enabled": False},
            {"domain": "test.example.com", "answer": "2001:db8::1"},
        ):
            with self.subTest(record=record), self.assertRaises(BootstrapError):
                dns.adguard_action("test.example.com", "192.0.2.1", [record])

    def test_journal_is_private_and_does_not_adopt_uncertain_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.json"
            operation = dns.Change("adguard", "/control/rewrite/add", {"domain": "test.example.com", "answer": "192.0.2.1"})
            client = Mock()
            client.request.side_effect = BootstrapError("connection lost")
            with self.assertRaises(BootstrapError):
                dns.execute_changes([operation], {"adguard": client}, path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            client.reset_mock()
            with self.assertRaisesRegex(BootstrapError, "uncertain"):
                dns.execute_changes([], {"adguard": client}, path)
            client.request.assert_not_called()

    def test_plan_does_not_write_and_apply_records_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.json"
            operation = dns.Change("adguard", "/control/rewrite/add", {"domain": "test.example.com", "answer": "192.0.2.1"})
            client = Mock()
            client.request.return_value = None
            dns.execute_changes([operation], {"adguard": client}, path)
            client.request.assert_called_once_with("POST", operation.path, operation.body)
            self.assertEqual(dns.read_journal(path)["created"][0]["provider"], "adguard")

    def test_http_failures_do_not_expose_credentials_or_response_body(self) -> None:
        client = dns.Api("https://dns.example.com", "Basic private-value")
        with patch.object(client.opener, "open", side_effect=OSError("private-value")), self.assertRaises(BootstrapError) as caught:
            client.request("GET", "/control/rewrite/list")
        self.assertNotIn("private-value", str(caught.exception))

    def test_all_provider_conflicts_are_checked_before_writes(self) -> None:
        client = Mock()
        client.request.return_value = [{"domain": "home.test.example.com", "answer": "192.0.2.99"}]
        zone = [{"id": "a" * 32, "name": "example.com"}]
        with (
            patch.object(dns, "Api", return_value=client),
            patch.object(dns, "cf_list", side_effect=[zone, [], [], [], [], []]),
            self.assertRaisesRegex(BootstrapError, "AdGuard DNS conflict"),
        ):
            dns.plan_changes(self.settings(), "192.0.2.1")
        self.assertTrue(all(call.args[0] == "GET" for call in client.request.call_args_list))

    def test_cloudflare_checks_explicit_names_that_override_wildcard(self) -> None:
        client = Mock()
        zone = [{"id": "a" * 32, "name": "example.com"}]
        conflicting = [{"name": "traefik.test.example.com", "type": "CNAME", "content": "other.example.com"}]
        with (
            patch.object(dns, "Api", return_value=client),
            patch.object(dns, "cf_list", side_effect=[zone, [], [], conflicting]),
            self.assertRaisesRegex(BootstrapError, "Cloudflare DNS conflict"),
        ):
            dns.plan_changes(self.settings(), "192.0.2.1")
        client.request.assert_not_called()

    def test_both_provider_payloads_and_unchanged_second_plan(self) -> None:
        client = Mock()
        client.request.return_value = []
        zone = [{"id": "a" * 32, "name": "example.com"}]
        with patch.object(dns, "Api", return_value=client), patch.object(dns, "cf_list", side_effect=[zone, [], [], [], [], []]):
            changes, _ = dns.plan_changes(self.settings(), "192.0.2.1")
        self.assertEqual(len(changes), 6)
        self.assertEqual([change.body["name"] for change in changes[:2]], ["test.example.com", "*.test.example.com"])
        self.assertTrue(all(change.body["proxied"] is False for change in changes[:2]))
        self.assertEqual([change.body["domain"] for change in changes[2:]], dns.names_for("test.example.com"))
        client.request.return_value = [change.body for change in changes[2:]]
        records = [[{**change.body, "id": "b" * 32}] for change in changes[:2]]
        with patch.object(dns, "Api", return_value=client), patch.object(dns, "cf_list", side_effect=[zone, *records, [], [], []]):
            repeated, _ = dns.plan_changes(self.settings(), "192.0.2.1")
        self.assertEqual(repeated, [])

    def test_cloudflare_pagination_and_unsuccessful_responses(self) -> None:
        client = Mock()
        client.request.side_effect = [
            {"success": True, "result": [{"id": "one"}], "result_info": {"total_pages": 2}},
            {"success": True, "result": [{"id": "two"}], "result_info": {"total_pages": 2}},
        ]
        self.assertEqual(len(dns.cf_list(client, "/zones", {})), 2)
        for document in ({"success": False, "result": []}, {"success": True, "result": "bad"}, {"success": True, "result": [], "result_info": None}):
            with self.subTest(document=document), self.assertRaises(BootstrapError):
                dns.cf_result(document)

    def test_read_only_plan_never_posts_or_creates_journal(self) -> None:
        settings = self.settings(cloudflare=False)
        client = Mock()
        client.request.return_value = []
        with tempfile.TemporaryDirectory() as directory, patch.object(dns, "Api", return_value=client), contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            dns.preview(settings, "192.0.2.1", root)
            self.assertFalse((root / "config/bootstrap-dns/test-host/journal.json").exists())
        self.assertTrue(all(call.args[0] == "GET" for call in client.request.call_args_list))

    def test_successful_adguard_apply_readback_and_target_binding(self) -> None:
        settings = self.settings(cloudflare=False)
        client = Mock()
        rewrites = []

        def request(method, path, body=None):
            if method == "GET":
                return rewrites.copy()
            rewrites.append(body)
            return None

        client.request.side_effect = request
        with tempfile.TemporaryDirectory() as directory, patch.object(dns, "Api", return_value=client), contextlib.redirect_stdout(io.StringIO()):
            root = Path(directory)
            dns.reconcile(settings, "192.0.2.1", root=root)
            journal = dns.read_journal(root / "config/bootstrap-dns/test-host/journal.json")
            self.assertEqual(len(journal["created"]), 4)
            self.assertNotIn("private-password", json.dumps(journal))
            dns.reconcile(settings, "192.0.2.1", root=root)
            self.assertEqual(sum(call.args[0] == "POST" for call in client.request.call_args_list), 4)
            settings.network = replace(settings.network, expected_ipv4="192.0.2.2")
            with self.assertRaisesRegex(BootstrapError, "target or providers changed"):
                dns.reconcile(settings, "192.0.2.2", root=root)

    def test_config_is_opt_in_and_rejects_unsafe_endpoints(self) -> None:
        self.assertEqual(config.load_dns_config({"mode": "external", "verify": True}, "test.example.com"), DnsConfig("external", True))
        for url in (
            "http://dns.example.com",
            "https://user:secret@dns.example.com",
            "https://dns.example.com/control",
            "https://dns.example.com?token=secret",
            "file:///tmp/dns",
            "https://dns.example.com:bad",
        ):
            with self.subTest(url=url), self.assertRaises(ConfigError):
                config.load_dns_config(
                    {"mode": "external", "verify": True, "adguard": {"url": url, "username": "operator", "password": "secret"}}, "test.example.com"
                )
        for url in ("https://dns.example.com", "http://127.0.0.1:3000", "http://[::1]:3000"):
            loaded = config.load_dns_config(
                {"mode": "external", "verify": True, "adguard": {"url": url, "username": "operator", "password": "secret"}}, "test.example.com"
            )
            self.assertEqual(loaded.adguard.url, url)
            self.assertNotIn("secret", repr(loaded))
        with self.assertRaises(ConfigError):
            config.load_dns_config({"mode": "external", "verify": True, "cloudflare": {"zone": "other.com"}}, "test.example.com")

    def test_managed_dns_is_default_and_requires_target_specific_providers(self) -> None:
        ag = {"url": "https://dns.example.com", "username": "operator", "password": "test-password"}
        self.assertEqual(config.load_dns_config({"adguard": ag}, "test.example.com").mode, "managed")
        loaded = config.load_dns_config({"adguard": ag, "cloudflare": {"zone": "example.com"}}, "test.example.com", "aws")
        self.assertEqual(loaded.mode, "managed")
        for target, providers in (
            ("aws", {"adguard": ag}),
            ("aws", {}),
            ("proxmox", {"adguard": ag, "cloudflare": {"zone": "example.com"}}),
        ):
            with self.subTest(target=target, providers=list(providers)), self.assertRaises(ConfigError):
                config.load_dns_config(providers, "test.example.com", target)

    def test_adguard_is_optional_for_both_targets(self) -> None:
        for target, providers in (("proxmox", {}), ("aws", {"cloudflare": {"zone": "example.com"}})):
            with self.subTest(target=target):
                loaded = config.load_dns_config(providers, "test.example.com", target)
                self.assertEqual(loaded.mode, "managed")
                self.assertIsNone(loaded.adguard)

    def test_enabled_switch_defaults_true_and_supports_explicit_disable(self) -> None:
        self.assertTrue(config.load_dns_config({}, "test.example.com").enabled)
        self.assertFalse(config.load_dns_config({"enabled": False}, "test.example.com", "aws").enabled)
        self.assertTrue(config.load_dns_config({"enabled": True, "cloudflare": {"zone": "example.com"}}, "test.example.com", "aws").enabled)
        for value in ("false", 0, 1, None):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                config.load_dns_config({"enabled": value}, "test.example.com")
        for enabled, mode in ((True, "external"), (False, "managed")):
            with self.subTest(enabled=enabled), self.assertRaises(ConfigError):
                config.load_dns_config({"enabled": enabled, "mode": mode}, "test.example.com")

    def test_proxmox_without_adguard_makes_no_api_calls_or_journal(self) -> None:
        settings = self.settings(cloudflare=False, adguard=False)
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(dns, "Api") as client,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            root = Path(directory)
            dns.preview(settings, None, root)
            dns.reconcile(settings, "192.0.2.1", root=root)
            self.assertFalse((root / "config/bootstrap-dns/test-host/journal.json").exists())
        client.assert_not_called()
        self.assertIn("0 creates", output.getvalue())

    def test_aws_without_adguard_plans_only_cloudflare_records(self) -> None:
        client = Mock()
        zone = [{"id": "a" * 32, "name": "example.com"}]
        with patch.object(dns, "Api", return_value=client) as api, patch.object(dns, "cf_list", side_effect=[zone, [], [], [], [], []]):
            changes, clients = dns.plan_changes(self.settings(adguard=False), "192.0.2.1")
        self.assertEqual(len(changes), 2)
        self.assertEqual(set(clients), {"cloudflare"})
        self.assertEqual(api.call_count, 1)
        client.request.assert_not_called()

    def test_proxmox_refuses_cloudflare_even_if_validation_was_bypassed(self) -> None:
        settings = self.settings()
        settings.target = "proxmox"
        with patch.object(dns, "Api") as client, self.assertRaisesRegex(BootstrapError, "DDNS"):
            dns.plan_changes(settings, "192.0.2.1")
        client.assert_not_called()

    def test_unknown_ip_preview_checks_both_providers_without_writes(self) -> None:
        client = Mock()
        client.request.return_value = []
        zone = [{"id": "a" * 32, "name": "example.com"}]
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(dns, "Api", return_value=client),
            patch.object(dns, "cf_list", side_effect=[zone, [], [], [], [], []]),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            dns.preview(self.settings(), None, Path(directory))
        self.assertIn("6 creates", output.getvalue())
        self.assertTrue(all(call.args[0] == "GET" for call in client.request.call_args_list))

    def test_managed_resolver_wait_is_bounded_and_never_writes_dns(self) -> None:
        settings = self.settings(cloudflare=False)
        settings.network = replace(settings.network, dns=replace(settings.network.dns, mode="managed"))
        plan = SimpleNamespace(config=settings)
        with (
            patch.object(network.socket, "getaddrinfo", return_value=[]),
            patch.object(network.time, "monotonic", side_effect=[0, 1, 3]),
            patch.object(network.time, "sleep") as sleep,
            self.assertRaisesRegex(BootstrapError, "Managed DNS resolver checkpoint"),
        ):
            network.verify_dns(plan, "192.0.2.1", wait_seconds=3)
        sleep.assert_called_once_with(2)

    def test_separate_dns_flags_are_removed(self) -> None:
        for flag in ("--dns-plan", "--dns-apply"):
            with patch("sys.argv", ["bootstrap", flag]), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                cli.parse_args()
        import yaml  # noqa: PLC0415

        taskfile = Path(__file__).resolve().parents[2] / "scripts/bootstrap/Taskfile.bootstrap.yaml"
        tasks = yaml.safe_load(taskfile.read_text())["tasks"]
        self.assertNotIn("dns-plan", tasks)
        self.assertNotIn("dns-apply", tasks)

    def test_disabled_dns_never_contacts_providers_or_writes_artifacts(self) -> None:
        settings = self.settings()
        settings.network = replace(settings.network, dns=replace(settings.network.dns, mode="external"))
        with tempfile.TemporaryDirectory() as directory, patch.object(dns, "Api") as api:
            root = Path(directory)
            dns.preview(settings, None, root)
            dns.reconcile(settings, "192.0.2.1", root=root)
            self.assertEqual(list(root.iterdir()), [])
        api.assert_not_called()

    def test_redirects_are_not_followed(self) -> None:
        self.assertIsNone(dns.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example.com"))

    def test_cloudflare_receipt_and_uncertain_failure(self) -> None:
        operation = dns.Change("cloudflare", "/zones/zone/dns_records", {"type": "A", "name": "test.example.com", "content": "192.0.2.1"})
        for result in ({"success": False}, {"success": True, "result": {"id": "bad"}}):
            with tempfile.TemporaryDirectory() as directory:
                client = Mock()
                client.request.return_value = result
                path = Path(directory) / "journal.json"
                with self.assertRaises(BootstrapError):
                    dns.execute_changes([operation], {"cloudflare": client}, path)
                with self.assertRaisesRegex(BootstrapError, "uncertain"):
                    dns.read_journal(path)
        with tempfile.TemporaryDirectory() as directory:
            client = Mock()
            client.request.return_value = {"success": True, "result": {"id": "a" * 32}}
            path = Path(directory) / "journal.json"
            dns.execute_changes([operation], {"cloudflare": client}, path)
            self.assertEqual(dns.read_journal(path)["created"][0]["record_id"], "a" * 32)

    def test_dns_requires_deployment_to_supply_a_valid_ipv4(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(BootstrapError, "verified deployment IPv4"):
            dns.reconcile(self.settings(), "auto", root=Path(directory))

    def test_adguard_readback_failure_is_not_retried(self) -> None:
        client = Mock()
        client.request.return_value = []
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(dns, "Api", return_value=client),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaisesRegex(BootstrapError, "readback"),
        ):
            dns.reconcile(self.settings(cloudflare=False), "192.0.2.1", root=Path(directory))
        self.assertEqual(sum(call.args[0] == "POST" for call in client.request.call_args_list), 4)


if __name__ == "__main__":
    unittest.main()
