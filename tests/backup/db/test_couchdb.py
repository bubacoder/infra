"""CouchDB append-only ordering and inventory consistency."""

# ruff: noqa: PT009, PT027

import json
import stat
from unittest.mock import patch

from scripts.backup import runner
from scripts.backup.common import BackupError
from scripts.backup.db import couchdb
from tests.backup.support import BackupTestCase


class CouchDBBackupTests(BackupTestCase):
    def test_couchdb_export_copies_indexes_before_shards_and_config(self) -> None:
        data = self.root / "couchdb/data"
        index = data / ".shards/00000000-ffffffff/notes.view"
        shard = data / "shards/00000000-ffffffff/notes.couch"
        index.parent.mkdir(parents=True)
        shard.parent.mkdir(parents=True)
        for path in (index, shard, data / "_dbs.couch", data / "_nodes.couch"):
            path.write_bytes(b"test append-only data")
        config = self.root / "couchdb/etc/local.ini"
        config.parent.mkdir(parents=True)
        config.write_text("[couchdb]\n")
        target = {"engine": "couchdb", "container": "couchdb", "data": "couchdb/data", "config": "couchdb/etc"}
        with patch.object(couchdb, "couchdb_databases", return_value=["_replicator", "_users", "notes"]):
            result = couchdb.export("database/couchdb", target, self.root, self.export_root)
        paths = [entry["file"] for entry in json.loads((result / "manifest.json").read_text())["files"]]
        self.assertEqual(paths[0], "couchdb/data/.shards/00000000-ffffffff/notes.view")
        self.assertLess(paths.index("couchdb/data/shards/00000000-ffffffff/notes.couch"), paths.index("couchdb/data/_dbs.couch"))
        self.assertIn("couchdb/etc/local.ini", paths)
        self.assertEqual(stat.S_IMODE((result / paths[0]).stat().st_mode), 0o600)
        self.assertEqual(runner.verify_latest("database/couchdb", target, self.root, self.export_root), result)

    def test_couchdb_change_during_copy_never_publishes_partial_export(self) -> None:
        data = self.root / "couchdb/data"
        shard = data / "shards/00000000-ffffffff/notes.couch"
        shard.parent.mkdir(parents=True)
        for path in (shard, data / "_dbs.couch", data / "_nodes.couch"):
            path.write_bytes(b"snapshot data")
        (self.root / "couchdb/etc").mkdir()
        target = {"engine": "couchdb", "container": "couchdb", "data": "couchdb/data", "config": "couchdb/etc"}
        with (
            patch.object(
                couchdb, "couchdb_databases", side_effect=[["_replicator", "_users", "notes"], ["_replicator", "_users", "new-db", "notes"]]
            ),
            self.assertRaisesRegex(BackupError, "inventory changed"),
        ):
            couchdb.export("database/couchdb", target, self.root, self.export_root)
        self.assertEqual([path.name for path in (self.export_root / "database-couchdb").iterdir()], [".lock"])
