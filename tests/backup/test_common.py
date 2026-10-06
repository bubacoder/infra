"""Private staging and streamed native artifact validation."""

# ruff: noqa: PT009, PT027

import os
from unittest.mock import patch

from scripts.backup import common
from tests.backup.support import BackupTestCase


class BackupCommonTests(BackupTestCase):
    def test_refuses_to_use_shared_or_symlinked_backup_directory(self) -> None:
        root = self.root / "db-backups"
        root.mkdir(mode=0o755)
        with self.assertRaises(common.BackupError):
            common.private_directory(root)
        root.rmdir()
        root.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(common.BackupError):
            common.private_directory(root)

    def test_docker_dump_rejects_empty_or_invalid_postgres_stream(self) -> None:
        with patch.object(common.subprocess, "run"), self.assertRaisesRegex(common.BackupError, "Empty export"):
            common.docker_dump(["docker", "exec", "test"], self.root / "empty.dump")
        with (
            patch.object(common.subprocess, "run", side_effect=lambda _command, **kwargs: os.write(kwargs["stdout"].fileno(), b"bad dump")),
            self.assertRaisesRegex(common.BackupError, "Invalid PostgreSQL dump"),
        ):
            common.docker_dump(["docker", "exec", "test"], self.root / "invalid.dump")
