"""Pure artifact rendering and stable fingerprints use only synthetic inputs."""

# ruff: noqa: PT009, PT027 -- unittest assertions

import json
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts.bootstrap.config import fingerprint, render_outputs

ROOT = Path(__file__).resolve().parents[2]


class RenderingTests(unittest.TestCase):
    def test_rendering_uses_resolved_inputs_without_external_access(self) -> None:
        config = yaml.safe_load((ROOT / "config-example/bootstrap-aws.yaml").read_text())
        secrets = {"cloudflare_token": "SYNTHETIC_TOKEN"}
        manifests = {"synthetic-manifest.yaml": "kind: ConfigMap\n"}
        with (
            patch("scripts.bootstrap.config.load_secret_files", side_effect=AssertionError("Unexpected credential read")),
            patch("scripts.bootstrap.config.public_key", side_effect=AssertionError("Unexpected key validation")),
            patch("scripts.bootstrap.config.traefik.manifests", side_effect=AssertionError("Unexpected projection read")),
            patch.object(Path, "open", side_effect=AssertionError("Unexpected file access")),
            patch("scripts.bootstrap.config.subprocess.run", side_effect=AssertionError("Unexpected subprocess")),
        ):
            rendered = render_outputs(config, secrets, "ssh-ed25519 SYNTHETIC_KEY", manifests)
        self.assertEqual(yaml.safe_load(rendered["secrets.yaml"]), secrets)
        self.assertEqual(rendered["synthetic-manifest.yaml"], manifests["synthetic-manifest.yaml"])
        self.assertEqual(json.loads(rendered["aws.tfvars.json"])["ssh_public_key"], "ssh-ed25519 SYNTHETIC_KEY")
        for name, content in rendered.items():
            if name != "secrets.yaml":
                self.assertNotIn("SYNTHETIC_TOKEN", content)
                self.assertNotIn("cloudflare-token", content)
        self.assertIn("cloudflare_token", config["dns"])
        self.assertEqual(secrets, {"cloudflare_token": "SYNTHETIC_TOKEN"})

    def test_fingerprint_is_order_independent_and_includes_private_inputs(self) -> None:
        rendered = {"host.yaml": "public", "secrets.yaml": "first synthetic credential"}
        self.assertEqual(fingerprint(rendered), fingerprint(dict(reversed(list(rendered.items())))))
        changed = {**rendered, "secrets.yaml": "rotated synthetic credential"}
        self.assertNotEqual(fingerprint(rendered), fingerprint(changed))
