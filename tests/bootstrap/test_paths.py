"""Managed paths preserve deployment identity and validate state read-only."""

# ruff: noqa: PT009, PT027 -- unittest assertions

import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from scripts.bootstrap.paths import BootstrapPathError, BootstrapPaths


class BootstrapPathsTests(unittest.TestCase):
    def setUp(self) -> None:
        preferred = Path("/tmp/opencode")  # noqa: S108 -- optional harness directory
        self.temp = tempfile.TemporaryDirectory(dir=preferred if preferred.is_dir() else None)
        self.addCleanup(self.temp.cleanup)
        self.deployment = Path(self.temp.name)
        self.paths = BootstrapPaths(self.deployment)

    def test_paths_and_plans_keep_the_original_deployment_identity(self) -> None:
        self.assertEqual(self.paths.deployment, self.deployment)
        self.assertEqual(self.paths.generated, self.deployment / "state/generated")
        self.assertEqual(self.paths.backups, self.deployment / "state/backups")
        for target, kind, name in (
            ("aws", "apply", "aws.tfplan"),
            ("aws", "destroy", "destroy.tfplan"),
            ("proxmox", "destroy", "proxmox-destroy-plan.json"),
        ):
            with self.subTest(target=target, kind=kind):
                self.assertEqual(self.paths.plan(target, kind), self.paths.plans / name)
        with self.assertRaises(FrozenInstanceError):
            self.paths.deployment = self.deployment / "other"

    def test_validation_never_creates_state_or_changes_permissions(self) -> None:
        self.paths.check_state()
        self.assertFalse(self.paths.state.exists())
        self.paths.state.mkdir(mode=0o700)
        self.paths.check_state()
        self.paths.state.chmod(0o755)
        with self.assertRaises(BootstrapPathError):
            self.paths.check_state()
        self.assertEqual(self.paths.state.stat().st_mode & 0o777, 0o755)

    def test_symlinks_and_regular_files_are_not_state_directories(self) -> None:
        self.paths.state.symlink_to(self.deployment, target_is_directory=True)
        with self.assertRaises(BootstrapPathError):
            self.paths.check_state()
        self.paths.state.unlink()
        self.paths.state.write_text("preserve")
        with self.assertRaises(BootstrapPathError):
            self.paths.check_state()
        self.assertEqual(self.paths.state.read_text(), "preserve")
