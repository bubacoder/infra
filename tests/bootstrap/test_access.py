"""Offline controller kubeconfig lifecycle and ownership coverage."""

# ruff: noqa: PT009, PT027 -- match bootstrap unittest fixtures

import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts.bootstrap.access import AccessError, install, remove, verify

TEMP_ROOT = Path("/tmp/opencode")  # noqa: S108 -- approved harness directory


class BootstrapAccessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=TEMP_ROOT if TEMP_ROOT.is_dir() else None)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory = self.root / "deployment"
        self.directory.mkdir(mode=0o700)
        self.home = self.root / "home"
        self.home.mkdir(mode=0o700)
        self.context = "k3s-lab"
        self.source = yaml.safe_dump(
            {
                "apiVersion": "v1",
                "kind": "Config",
                "clusters": [{"name": "default", "cluster": {"server": "https://127.0.0.1:6443", "certificate-authority-data": "FAKE_CA"}}],
                "users": [{"name": "default", "user": {"client-certificate-data": "FAKE_CERT", "client-key-data": "FAKE_KEY"}}],
                "contexts": [{"name": "default", "context": {"cluster": "default", "user": "default"}}],
                "current-context": "default",
            },
            sort_keys=False,
        ).encode()

    def install(self, source=None, host="k3s.example.com"):
        return install(source or self.source, self.directory, self.context, host, "k3s-host", self.home)

    @patch("scripts.bootstrap.access.check_node")
    def test_new_cluster_creates_unique_context_and_private_files(self, check):
        self.assertTrue(self.install())
        kube = self.home / ".kube"
        merged = yaml.safe_load((kube / "config").read_text())
        self.assertEqual(merged["current-context"], self.context)
        self.assertEqual(merged["clusters"][0]["name"], self.context)
        self.assertEqual(merged["users"][0]["name"], self.context)
        self.assertEqual(merged["contexts"][0]["context"], {"cluster": self.context, "user": self.context})
        self.assertEqual(merged["clusters"][0]["cluster"]["server"], "https://k3s.example.com:6443")
        self.assertEqual(stat.S_IMODE(kube.stat().st_mode), 0o700)
        for path in (kube / "config", kube / f"{self.context}.yaml", self.directory / "k3s-access-receipt.json"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(json.loads((self.directory / "k3s-access-receipt.json").read_text())["context"], self.context)
        self.assertEqual(check.call_count, 1)
        verify(self.directory, self.context, "k3s-host", self.home)
        self.assertEqual(check.call_count, 3)

    @patch("scripts.bootstrap.access.check_node")
    def test_repeat_is_idempotent_and_refresh_preserves_existing_context(self, check):
        kube = self.home / ".kube"
        kube.mkdir(mode=0o700)
        original = {
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [{"name": "other", "cluster": {"server": "https://other"}}],
            "users": [{"name": "other", "user": {"token": "OTHER_SECRET"}}],
            "contexts": [{"name": "other", "context": {"cluster": "other", "user": "other"}}],
            "current-context": "other",
        }
        (kube / "config").write_text(yaml.safe_dump(original))
        (kube / "config").chmod(0o600)
        self.assertTrue(self.install())
        before = (kube / "config").read_bytes()
        backups = set(self.directory.glob("k3s-access-backup-*.yaml"))
        self.assertEqual(len(backups), 1)
        self.assertFalse(self.install())
        self.assertEqual((kube / "config").read_bytes(), before)
        self.assertEqual(set(self.directory.glob("k3s-access-backup-*.yaml")), backups)
        refreshed = self.source.replace(b"FAKE_CERT", b"NEW_CERT")
        self.assertTrue(self.install(refreshed))
        merged = yaml.safe_load((kube / "config").read_text())
        self.assertEqual(merged["current-context"], "other")
        self.assertEqual(merged["users"][0], original["users"][0])
        self.assertEqual(merged["users"][1]["user"]["client-certificate-data"], "NEW_CERT")
        self.assertEqual(len(set(self.directory.glob("k3s-access-backup-*.yaml"))), 2)
        self.assertEqual(check.call_count, 3)

    @patch("scripts.bootstrap.access.check_node")
    def test_refuses_collisions_without_receipt_and_does_not_modify_existing(self, check):
        kube = self.home / ".kube"
        kube.mkdir(mode=0o700)
        existing = {"clusters": [{"name": self.context, "cluster": {"server": "https://other"}}], "users": [], "contexts": []}
        data = yaml.safe_dump(existing).encode()
        (kube / "config").write_bytes(data)
        (kube / "config").chmod(0o600)
        with self.assertRaisesRegex(AccessError, "unowned"):
            self.install()
        self.assertEqual((kube / "config").read_bytes(), data)
        self.assertFalse((self.directory / "k3s-access-receipt.json").exists())
        check.assert_not_called()

    @patch("scripts.bootstrap.access.check_node")
    def test_refuses_human_changes_to_owned_credentials(self, check):
        self.install()
        merged = self.home / ".kube/config"
        text = merged.read_text().replace("FAKE_CERT", "HUMAN_EDIT")
        merged.write_text(text)
        with self.assertRaisesRegex(AccessError, "changed outside bootstrap"):
            self.install()
        self.assertEqual(merged.read_text(), text)
        self.assertEqual(check.call_count, 1)
        with self.assertRaisesRegex(AccessError, "differs"):
            verify(self.directory, self.context, "k3s-host", self.home)

    @patch("scripts.bootstrap.access.check_node")
    def test_failed_tls_or_credentials_validation_leaves_no_receipt(self, check):
        check.side_effect = AccessError("TLS failure")
        with self.assertRaises(AccessError):
            self.install()
        self.assertFalse((self.directory / "k3s-access-receipt.json").exists())
        self.assertFalse((self.home / ".kube/config").exists())

    @patch("scripts.bootstrap.access.check_node")
    def test_refuses_insecure_source_before_network_or_file_changes(self, check):
        source = yaml.safe_load(self.source)
        source["clusters"][0]["cluster"]["insecure-skip-tls-verify"] = True
        with self.assertRaisesRegex(AccessError, "TLS verification"):
            self.install(yaml.safe_dump(source).encode())
        check.assert_not_called()
        self.assertFalse((self.directory / "k3s-access-receipt.json").exists())

    @patch("scripts.bootstrap.access.check_node")
    def test_cleanup_removes_only_owned_context_and_keeps_recovery_receipt(self, check):
        kube = self.home / ".kube"
        kube.mkdir(mode=0o700)
        original = {
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [{"name": "other", "cluster": {"server": "https://other"}}],
            "users": [{"name": "other", "user": {"token": "OTHER_SECRET"}}],
            "contexts": [{"name": "other", "context": {"cluster": "other", "user": "other"}}],
            "current-context": "other",
        }
        (kube / "config").write_text(yaml.safe_dump(original))
        (kube / "config").chmod(0o600)
        self.install()
        self.assertTrue(remove(self.directory, self.context, "k3s-host", self.home))
        merged = yaml.safe_load((kube / "config").read_text())
        self.assertEqual(merged["current-context"], "other")
        for key in ("clusters", "users", "contexts"):
            self.assertEqual(merged[key], original[key])
        self.assertFalse((kube / f"{self.context}.yaml").exists())
        self.assertTrue((self.directory / "k3s-access-receipt.json").exists())
        self.assertFalse(remove(self.directory, self.context, "k3s-host", self.home))
        check.assert_called_once()

    @patch("scripts.bootstrap.access.check_node")
    def test_cleanup_preserves_modified_credential_and_other_context_references(self, check):
        self.install()
        merged = self.home / ".kube/config"
        text = merged.read_text().replace("FAKE_CERT", "HUMAN_EDIT")
        merged.write_text(text)
        with self.assertRaisesRegex(AccessError, "differs"):
            remove(self.directory, self.context, "k3s-host", self.home)
        self.assertEqual(merged.read_text(), text)
        self.assertTrue((self.home / ".kube" / f"{self.context}.yaml").exists())
        check.assert_called_once()

    @patch("scripts.bootstrap.access.check_node")
    def test_cleanup_refuses_other_context_referencing_owned_user(self, check):
        self.install()
        merged = self.home / ".kube/config"
        data = yaml.safe_load(merged.read_text())
        data["contexts"].append({"name": "other", "context": {"cluster": self.context, "user": self.context}})
        merged.write_text(yaml.safe_dump(data))
        with self.assertRaisesRegex(AccessError, "Another context"):
            remove(self.directory, self.context, "k3s-host", self.home)
        self.assertEqual(yaml.safe_load(merged.read_text()), data)
        check.assert_called_once()

    @patch("scripts.bootstrap.access.check_node")
    def test_rejects_symlinked_credential_file(self, check):
        kube = self.home / ".kube"
        kube.mkdir(mode=0o700)
        outside = self.root / "outside"
        outside.write_text("KEEP")
        (kube / "config").symlink_to(outside)
        with self.assertRaisesRegex(Exception, "regular files"):
            self.install()
        self.assertEqual(outside.read_text(), "KEEP")
        check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
