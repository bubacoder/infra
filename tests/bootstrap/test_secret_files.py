"""File-only credential references; all data/files here are synthetic."""

# ruff: noqa: PT009, PT019, PT027, S106 -- unittest assertions and explicit sentinels

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts.bootstrap.config import MAX_SECRET_BYTES, ConfigError, Configuration, main, read_secret_file

ROOT = Path(__file__).resolve().parents[2]


class SecretFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp/opencode" if Path("/tmp/opencode").is_dir() else None)  # noqa: S108
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "config-example", self.root / "config-example")
        shutil.copytree(ROOT / "ansible/roles", self.root / "ansible/roles")
        self.directory = self.root / "config/test"
        self.config = Configuration(self.root, self.directory, "proxmox")
        self.config.init()
        self.secret_dir = self.directory / "secrets"
        self.secret_dir.mkdir(mode=0o700)
        self.token = self.secret_dir / "cloudflare-token"
        self.token.write_bytes(b"SYNTHETIC_TOKEN\r\n\r\n")
        self.token.chmod(0o600)

    def edit(self, callback):
        value = yaml.safe_load(self.config.source.read_text())
        callback(value)
        self.config.source.write_text(yaml.safe_dump(value, sort_keys=False))

    def test_relative_reference_and_trimmed_crlf_are_separated_from_public_artifacts(self):
        self.config.prepare()
        secrets = yaml.safe_load((self.config.generated / "secrets.yaml").read_text())
        self.assertEqual(secrets, {"cloudflare_token": "SYNTHETIC_TOKEN"})
        host = (self.config.generated / "host.yaml").read_text()
        self.assertNotIn("cloudflare_token", host)
        self.assertNotIn("cloudflare-token", host)
        self.assertNotIn("SYNTHETIC_TOKEN", host)
        self.assertNotIn("SYNTHETIC_TOKEN", self.config.source.read_text())
        self.assertEqual((self.config.generated / "secrets.yaml").stat().st_mode & 0o777, 0o600)

    def test_password_spaces_and_interior_newlines_are_preserved(self):
        password = self.secret_dir / "password"
        password.write_bytes(b"  first\r\nsecond \t\r\n")
        password.chmod(0o400)
        self.edit(lambda v: v["dns"].update(adguard_password={"file": "./secrets/password"}))
        self.config.prepare()
        secrets = yaml.safe_load((self.config.generated / "secrets.yaml").read_text())
        self.assertEqual(secrets["adguard_password"], "  first\r\nsecond \t")

    def test_absolute_and_tilde_references(self):
        for path in (str(self.token), "~/config/test/secrets/cloudflare-token"):
            with self.subTest(path=path), patch.dict(os.environ, {"HOME": str(self.root)}):
                self.edit(lambda v, path=path: v["dns"].update(cloudflare_token={"file": path}))
                self.config.prepare()
                self.assertEqual(yaml.safe_load((self.config.generated / "secrets.yaml").read_text())["cloudflare_token"], "SYNTHETIC_TOKEN")

    def test_inspection_never_opens_or_requires_referenced_secret_files(self):
        self.edit(lambda v: v["dns"].update(cloudflare_token={"file": "SENTINEL_PRIVATE_PATH"}))
        with patch("scripts.bootstrap.config.load_secret_files", side_effect=AssertionError("Inspection must not resolve references")):
            result = self.config.show()
            self.config.load()
        self.assertNotIn("SENTINEL_PRIVATE_PATH", json.dumps(result))
        self.assertFalse(self.config.generated.exists())

    def test_literals_and_ambiguous_references_are_rejected_even_when_feature_disabled(self):
        for reference in (
            "SENTINEL_LITERAL",
            None,
            [],
            {},
            {"file": ""},
            {"file": 1},
            {"file": "secret\npath"},
            {"file": "secret", "value": "SENTINEL_LITERAL"},
        ):
            with self.subTest(reference=reference):
                self.edit(
                    lambda v, reference=reference: v.update(roles=[], services=[], host={}, dns={"enabled": False, "adguard_password": reference})
                )
                with self.assertRaises(ConfigError) as error:
                    self.config.show()
                self.assertNotIn("SENTINEL_LITERAL", str(error.exception))

    def test_obsolete_secrets_section_is_rejected_without_rendering_values(self):
        self.edit(lambda v: v.update(secrets={"cloudflare_token": "SENTINEL_LITERAL"}))
        with self.assertRaisesRegex(ConfigError, "obsolete secrets section") as error:
            self.config.show()
        self.assertNotIn("SENTINEL_LITERAL", str(error.exception))

    def test_missing_empty_binary_and_nul_secrets_fail_before_artifacts_or_provider_access(self):
        for content in (None, b"", b"\r\n", b"SENTINEL_CONTENT\x00", b"\xffSENTINEL_CONTENT"):
            with self.subTest(content=content):
                self.token.unlink(missing_ok=True)
                if content is not None:
                    self.token.write_bytes(content)
                    self.token.chmod(0o600)
                with patch("scripts.bootstrap.config.subprocess.run") as native, self.assertRaises(ConfigError) as error:
                    self.config.run("plan")
                native.assert_not_called()
                self.assertNotIn("SENTINEL_CONTENT", str(error.exception))
                self.assertFalse(self.config.generated.exists())

    def test_secret_permissions_are_exactly_0400_or_0600(self):
        for mode in (0o644, 0o640, 0o700, 0o000):
            with self.subTest(mode=mode):
                self.token.chmod(mode)
                with self.assertRaises(ConfigError):
                    self.config.prepare()
        for mode in (0o400, 0o600):
            self.token.chmod(mode)
            self.config.prepare()

    def test_secret_file_and_parent_symlinks_are_rejected(self):
        link = self.directory / "linked-token"
        link.symlink_to(self.token)
        alias = self.directory / "linked-directory"
        alias.symlink_to(self.secret_dir, target_is_directory=True)
        for path in (link, alias / self.token.name):
            with self.subTest(path=path):
                self.edit(lambda v, path=path: v["dns"].update(cloudflare_token={"file": str(path)}))
                with self.assertRaises(ConfigError):
                    self.config.prepare()

    def test_failed_secret_load_preserves_existing_generated_artifacts(self):
        self.config.prepare()
        before = {path.name: path.read_bytes() for path in self.config.generated.iterdir()}
        self.token.unlink()
        with self.assertRaises(ConfigError):
            self.config.prepare()
        self.assertEqual({path.name: path.read_bytes() for path in self.config.generated.iterdir()}, before)

    def test_parent_replaced_by_symlink_before_open_is_rejected(self):
        original_open = os.open
        original = self.directory / "original-secrets"

        def replace_parent(path, flags, *args, **kwargs):
            if path == "secrets":
                self.secret_dir.rename(original)
                self.secret_dir.symlink_to(original, target_is_directory=True)
            return original_open(path, flags, *args, **kwargs)

        with patch("scripts.bootstrap.config.os.open", side_effect=replace_parent), self.assertRaises(ConfigError):
            self.config.prepare()
        self.assertFalse(self.config.generated.exists())

    def test_open_parent_descriptor_cannot_be_redirected_by_replacement_symlink(self):
        original_open = os.open
        replacement = self.directory / "replacement"
        replacement.mkdir(mode=0o700)
        (replacement / self.token.name).write_text("WRONG_SYNTHETIC_TOKEN")
        (replacement / self.token.name).chmod(0o600)

        def replace_parent(path, flags, *args, **kwargs):
            if path == self.token.name:
                self.secret_dir.rename(self.directory / "original-secrets")
                self.secret_dir.symlink_to(replacement, target_is_directory=True)
            return original_open(path, flags, *args, **kwargs)

        with patch("scripts.bootstrap.config.os.open", side_effect=replace_parent):
            value = read_secret_file(str(self.token), self.directory)
        self.assertEqual(value, "SYNTHETIC_TOKEN")

    def test_secret_file_must_belong_to_the_current_user(self):
        with patch("scripts.bootstrap.config.os.geteuid", return_value=os.geteuid() + 1), self.assertRaises(ConfigError):
            self.config.prepare()

    def test_nonregular_and_oversized_secret_files_are_rejected(self):
        self.token.unlink()
        os.mkfifo(self.token, mode=0o600)
        with self.assertRaises(ConfigError):
            self.config.prepare()
        self.token.unlink()
        self.token.write_bytes(b"A" * (MAX_SECRET_BYTES + 1))
        self.token.chmod(0o600)
        with self.assertRaises(ConfigError):
            self.config.prepare()

    def test_cli_errors_do_not_reveal_secret_paths_or_contents(self):
        self.edit(lambda v: v["dns"].update(cloudflare_token={"file": "SENTINEL_PRIVATE_PATH"}))
        stream = io.StringIO()
        with (
            contextlib.redirect_stderr(stream),
            patch.dict(os.environ, {"BOOTSTRAP_DIR": str(self.directory), "BOOTSTRAP_TARGET": "proxmox"}),
            patch("scripts.bootstrap.config.ROOT", self.root),
            patch("sys.argv", ["config.py", "prepare"]),
        ):
            self.assertEqual(main(), 1)
        self.assertNotIn("SENTINEL_PRIVATE_PATH", stream.getvalue())
        self.assertIn("dns.cloudflare_token", stream.getvalue())

    @patch("scripts.bootstrap.config.public_key", return_value="ssh-ed25519 SYNTHETIC")
    def test_secret_file_rotation_invalidates_a_reviewed_plan(self, _key):
        value = yaml.safe_load((self.root / "config-example/bootstrap-aws.yaml").read_text())
        value["dns"]["cloudflare_token"] = {"file": str(self.token)}
        self.config.source.write_text(yaml.safe_dump(value))
        self.config = Configuration(self.root, self.directory, "aws")
        plan = self.config.state / "plans/aws.tfplan"

        def native(command, **_kwargs):
            plan.write_bytes(b"SYNTHETIC_PLAN")
            return subprocess.CompletedProcess(command, 0)

        with patch("scripts.bootstrap.config.subprocess.run", side_effect=native) as run:
            self.config.run("plan")
            self.token.write_text("ROTATED_SYNTHETIC_TOKEN\n")
            with self.assertRaisesRegex(ConfigError, "changed since review"):
                self.config.run("apply")
            self.assertEqual(run.call_count, 1)

    def test_secret_rotation_during_planning_never_creates_an_approval_receipt(self):
        plan = self.config.paths.plan("proxmox", "destroy")

        def native(command, **_kwargs):
            plan.write_bytes(b"SYNTHETIC_PLAN")
            self.token.write_text("ROTATED_SYNTHETIC_TOKEN\n")
            return subprocess.CompletedProcess(command, 0)

        with (
            patch("scripts.bootstrap.config.subprocess.run", side_effect=native),
            self.assertRaisesRegex(ConfigError, "Inputs changed during planning"),
        ):
            self.config.run("destroy-plan")
        self.assertTrue(plan.exists())
        self.assertFalse((self.config.state / "destroy-inputs.json").exists())
