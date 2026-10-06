"""MongoDB archive integrity and writer/credential cleanup."""

# ruff: noqa: PT009, PT027

import gzip
import hashlib
import subprocess
from unittest.mock import patch

from scripts.backup import runner
from scripts.backup.common import BackupError
from scripts.backup.db import mongodb
from tests.backup.support import BackupTestCase


class MongoDBBackupTests(BackupTestCase):
    def test_mongodb_archive_detects_truncated_gzip(self) -> None:
        path = self.root / "database.archive.gz"
        data = gzip.compress(b"test Mongo archive")
        path.write_bytes(data)
        mongodb.verify_mongo_archive(path)
        path.write_bytes(data[:-2])
        with self.assertRaisesRegex(BackupError, "Invalid compressed MongoDB archive"):
            mongodb.verify_mongo_archive(path)

    def test_mongodb_export_restarts_paused_writer_on_success_and_failure(self) -> None:
        (self.root / "unifi-network-application/data").mkdir(parents=True)
        target = {
            "engine": "mongodb",
            "container": "mongodb",
            "writer": "unifi-network-application",
            "paired_root": "unifi-network-application",
            "paired_files": ["data"],
        }
        placeholder = "test-only-value"

        def dump(command, destination):
            self.assertNotIn(placeholder, " ".join(command))
            data = gzip.compress(b"test Mongo archive")
            destination.write_bytes(data)
            return {"file": destination.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

        with (
            patch.object(mongodb, "container_environment", side_effect=["root", placeholder]),
            patch.object(mongodb, "docker_is_running", side_effect=[True, False]),
            patch.object(mongodb.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as commands,
            patch.object(mongodb, "docker_dump", side_effect=dump),
        ):
            directory = mongodb.export("database/mongodb", target, self.root, self.export_root)
        actions = [call.args[0][1] for call in commands.call_args_list]
        self.assertLess(actions.index("stop"), actions.index("start"))
        self.assertEqual({path.name for path in directory.iterdir()}, {"database.archive.gz", "manifest.json"})
        self.assertEqual(runner.verify_latest("database/mongodb", target, self.root, self.export_root), directory)
        self.assertNotIn(placeholder, repr(commands.call_args_list))
        with (
            patch.object(mongodb, "container_environment", side_effect=["root", placeholder]),
            patch.object(mongodb, "docker_is_running", side_effect=[True, False]),
            patch.object(mongodb.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as commands,
            patch.object(mongodb, "docker_dump", side_effect=BackupError("dump failed")),
            self.assertRaisesRegex(BackupError, "dump failed"),
        ):
            mongodb.export("database/mongodb", target, self.root, self.export_root)
        actions = [call.args[0][1] for call in commands.call_args_list]
        self.assertLess(actions.index("stop"), actions.index("start"))
        self.assertEqual(len([path for path in directory.parent.iterdir() if path.is_dir()]), 1)
