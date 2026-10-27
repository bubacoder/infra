"""Offline Traefik profile validation and shared-policy projections."""

# ruff: noqa: PT009, PT027, S106 -- unittest and synthetic credential sentinel

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts.bootstrap.config import ConfigError, outputs, validate

ROOT = Path(__file__).resolve().parents[2]


def profile(target="proxmox"):
    value = yaml.safe_load((ROOT / f"config-example/bootstrap-{target}.yaml").read_text())
    value.update(
        roles=["debian_base", "k3s", "k3s_traefik"],
        services=[],
        dns={"enabled": False},
        host={"acme_email": "synthetic@example.invalid"},
        secrets={"cloudflare_token": "SYNTHETIC_TOKEN_NOT_REAL"},
    )
    value["k3s"] = {
        "traefik": {
            "enabled": True,
            "domain": "apps.example.invalid",
            "admin_cidr": "192.0.2.10/32",
            "middlewares": ["localaccess", "https-only", "security-headers"],
            "acme_environment": "staging",
            "storage_class": "local-path",
            "storage_size": "1Gi",
        }
    }
    return value


class TraefikTests(unittest.TestCase):
    def test_profile_requires_only_feature_inputs_and_never_exports_token(self):
        for target in ("proxmox", "aws"):
            with self.subTest(target=target):
                value = profile(target)
                # AWS projection normally validates the SSH public key; this test
                # exercises validation only there, with no real key/provider reads.
                validate(value, target)
        rendered = outputs(profile())
        for name, content in rendered.items():
            if name != "secrets.yaml":
                self.assertNotIn("SYNTHETIC_TOKEN_NOT_REAL", content)
        self.assertIn("k3s-traefik-configmap.yaml", rendered)
        self.assertIn("k3s-traefik-pvc.yaml", rendered)
        self.assertIn("k3s-traefik-helmchartconfig.yaml", rendered)

    def test_configmap_reuses_complete_shared_policy_without_jinja_rendering(self):
        rendered = outputs(profile())
        cm = yaml.safe_load(rendered["k3s-traefik-configmap.yaml"])
        dynamic = yaml.safe_load(cm["data"]["middlewares.yaml"])
        canonical = yaml.safe_load((ROOT / "docker/security/traefik/config/dynamic/middlewares.yml").read_text())
        selected = dynamic["http"]["middlewares"]
        self.assertEqual(set(selected), {"localaccess", "local-ip-allowlist", "https-only", "security-headers"})
        for name, definition in selected.items():
            self.assertEqual(definition, canonical["http"]["middlewares"][name])
        self.assertEqual(dynamic["tls"], canonical["tls"])
        self.assertNotIn("serversTransports", dynamic["http"])
        self.assertIn('{{env "LOCAL_ACCESS_ADMIN_CIDR"}}', cm["data"]["middlewares.yaml"])
        self.assertEqual(cm["data"]["tls.yaml"], (ROOT / "docker/security/traefik/config/dynamic/tls.yml").read_text())

    def test_helm_values_are_single_writer_persistent_and_secret_referenced(self):
        rendered = outputs(profile())
        hcc = yaml.safe_load(rendered["k3s-traefik-helmchartconfig.yaml"])
        values = yaml.safe_load(hcc["spec"]["valuesContent"])
        self.assertEqual(values["deployment"]["replicas"], 1)
        self.assertEqual(values["updateStrategy"], {"type": "Recreate", "rollingUpdate": None})
        self.assertTrue(values["persistence"]["enabled"])
        pvc = yaml.safe_load(rendered["k3s-traefik-pvc.yaml"])
        self.assertEqual(values["persistence"]["existingClaim"], pvc["metadata"]["name"])
        self.assertEqual(pvc["spec"]["storageClassName"], "local-path")
        self.assertEqual(values["env"][-1]["valueFrom"]["secretKeyRef"], {"name": "bootstrap-traefik-cloudflare", "key": "token"})
        acme = values["certificatesResolvers"]["letsencrypt"]["acme"]
        self.assertEqual(acme["storage"], "/data/acme-staging.json")
        self.assertIn("staging", acme["caServer"])
        self.assertFalse(values["providers"]["kubernetesCRD"]["allowCrossNamespace"])

    def test_invalid_inputs_are_rejected_without_private_values(self):
        cases = [
            ("domain", "Bad Domain"),
            ("admin_cidr", "0.0.0.0/0"),
            ("storage_class", ""),
            ("storage_size", "0Gi"),
            ("acme_environment", "automatic"),
            ("middlewares", ["publicaccess"]),
            ("middlewares", ["localaccess-authentik"]),
            ("middlewares", ["missing"]),
            ("middlewares", ["localaccess", "localaccess"]),
        ]
        for key, setting in cases:
            with self.subTest(key=key, setting=setting):
                value = profile()
                value["k3s"]["traefik"][key] = setting
                with self.assertRaises(ConfigError):
                    outputs(value)
        for change in (
            lambda v: v["secrets"].clear(),
            lambda v: v["host"].clear(),
            lambda v: v["roles"].reverse(),
            lambda v: v["roles"].remove("k3s_traefik"),
        ):
            value = profile()
            change(value)
            with self.assertRaises(ConfigError):
                validate(value, "proxmox")

    def test_enabled_role_and_flag_must_agree(self):
        for enabled in (False, None):
            value = profile()
            value["k3s"]["traefik"] = {"enabled": enabled}
            with self.assertRaises(ConfigError):
                validate(value, "proxmox")

    def test_staging_to_production_uses_a_separate_account_file(self):
        value = profile()
        before = copy.deepcopy(value)
        value["k3s"]["traefik"]["acme_environment"] = "production"
        values = yaml.safe_load(yaml.safe_load(outputs(value)["k3s-traefik-helmchartconfig.yaml"])["spec"]["valuesContent"])
        self.assertEqual(values["certificatesResolvers"]["letsencrypt"]["acme"]["storage"], "/data/acme.json")
        self.assertEqual(before["k3s"]["traefik"]["acme_environment"], "staging")

    def test_claim_size_uses_api_canonical_quantity_for_repeatability(self):
        for requested, canonical in (("1024Mi", "1Gi"), ("1024Gi", "1Ti"), ("256Mi", "256Mi")):
            value = profile()
            value["k3s"]["traefik"]["storage_size"] = requested
            claim = yaml.safe_load(outputs(value)["k3s-traefik-pvc.yaml"])
            self.assertEqual(claim["spec"]["resources"]["requests"]["storage"], canonical)

    def test_broken_dependency_graphs_fail_without_echoing_names_or_values(self):
        source_path = ROOT / "docker/security/traefik/config/dynamic/middlewares.yml"
        original = yaml.safe_load(source_path.read_text())
        read_text = Path.read_text
        for dependencies in (["localaccess"], ["SENTINEL_DO_NOT_LOG"]):
            changed = copy.deepcopy(original)
            changed["http"]["middlewares"]["localaccess"]["chain"]["middlewares"] = dependencies

            def read(path, *args, fixture=changed, **kwargs):
                return yaml.safe_dump(fixture) if path == source_path else read_text(path, *args, **kwargs)

            with self.subTest(dependencies=dependencies), patch.object(Path, "read_text", read), self.assertRaises(ConfigError) as error:
                outputs(profile())
            self.assertNotIn("SENTINEL_DO_NOT_LOG", str(error.exception))

    def test_aws_projection_keeps_acme_credentials_out_of_terraform(self):
        with patch("scripts.bootstrap.config.public_key", return_value="ssh-ed25519 SYNTHETIC_PUBLIC_KEY"):
            rendered = outputs(profile("aws"))
        self.assertNotIn("SYNTHETIC_TOKEN_NOT_REAL", rendered["aws.tfvars.json"])
        self.assertNotIn("apps.example.invalid", rendered["aws.tfvars.json"])
        self.assertIn("k3s-traefik-configmap.yaml", rendered)
