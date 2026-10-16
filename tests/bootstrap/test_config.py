"""Focused regression tests for bootstrap document dispatch and validation."""

# ruff: noqa: PT009, PT027

import unittest
from pathlib import Path
from unittest.mock import patch, sentinel

from scripts.bootstrap import config
from scripts.bootstrap.core import ConfigError


class ConfigDispatchTests(unittest.TestCase):
    def document(self, version: int = 1) -> dict:
        return {"version": version, "deployment": {}, "vm": {}, "network": {}, "host": {}, "tls": {}}

    def test_dispatches_supported_versions_and_targets(self) -> None:
        for version, target in ((1, None), (2, "proxmox"), (2, "aws")):
            with self.subTest(version=version, target=target):
                document = self.document(version)
                if target is not None:
                    document["target"] = target
                loader = "load_aws_config" if target == "aws" else "load_proxmox_config"
                with patch.object(config, loader, return_value=sentinel.loaded) as load:
                    source = Path("config/bootstrap.yaml")
                    self.assertIs(config.parse_document(document, source), sentinel.loaded)
                load.assert_called_once_with(document, source)

    def test_rejects_target_errors_before_target_specific_validation(self) -> None:
        cases = (
            ({"version": True}, "version must be 1 or 2"),
            ({"version": 1, "target": "proxmox"}, "version 1 supports Proxmox only"),
            ({"version": 1, "aws": {}}, "version 1 supports Proxmox only"),
            ({"version": 2}, "version 2 requires target"),
            ({"version": 2, "target": "other"}, "target must be proxmox or aws"),
        )
        for overrides, message in cases:
            with self.subTest(overrides=overrides):
                document = self.document()
                document.update(overrides)
                with self.assertRaisesRegex(ConfigError, message):
                    config.parse_document(document, Path("config/bootstrap.yaml"))

    def test_mapping_reports_unknown_fields_before_missing_fields(self) -> None:
        with self.assertRaisesRegex(ConfigError, "test contains unknown fields: a, z"):
            config.require_mapping({"z": None, "a": None}, "test", {"required"}, {"required"})

    def test_domain_normalization_and_validation(self) -> None:
        self.assertEqual(config.validate_domain(" Example.COM.. "), "example.com")
        for domain in ("localhost", "example..com", "-example.com"):
            with self.subTest(domain=domain), self.assertRaisesRegex(ConfigError, "network.domain must be a valid domain name"):
                config.validate_domain(domain)


if __name__ == "__main__":
    unittest.main()
