"""SQLite WAL snapshots and application-owned paired state."""

# ruff: noqa: PT009, PT027

import contextlib
import json
import sqlite3
import stat

from scripts.backup import runner
from scripts.backup.apps import open_webui, vaultwarden
from scripts.backup.common import BackupError
from scripts.backup.db import sqlite
from tests.backup.support import BackupTestCase


class SQLiteBackupTests(BackupTestCase):
    def test_sqlite_online_backup_in_wal_mode_and_paired_file_inventory(self) -> None:
        data = self.root / "vaultwarden"
        data.mkdir()
        (data / "attachments").mkdir()
        (data / "sends").mkdir()
        (data / "rsa_key.pem").write_text("test signing key")
        target = {"engine": "sqlite", "database": "vaultwarden/db.sqlite3"}
        with contextlib.closing(sqlite3.connect(data / "db.sqlite3")) as live:
            live.execute("PRAGMA journal_mode=WAL")
            live.execute("CREATE TABLE vault (id INTEGER PRIMARY KEY, value TEXT)")
            live.execute("INSERT INTO vault(value) VALUES ('first')")
            live.commit()
            live.execute("INSERT INTO vault(value) VALUES ('second')")
            live.commit()
            export = vaultwarden.export("tools/vaultwarden", target, self.root, self.export_root)
            self.assertFalse((self.root / "db-backups").exists())
            live.execute("INSERT INTO vault(value) VALUES ('third')")
            live.commit()
        with contextlib.closing(sqlite3.connect(export / "database.sqlite3")) as restored:
            self.assertEqual(restored.execute("SELECT count(*) FROM vault").fetchone(), (2,))
        manifest = json.loads((export / "manifest.json").read_text())
        self.assertEqual(manifest["paired_files"], ["attachments", "rsa_key.pem", "sends"])
        self.assertEqual({path.name for path in export.iterdir()}, {"database.sqlite3", "manifest.json"})
        self.assertEqual(stat.S_IMODE((export / "database.sqlite3").stat().st_mode), 0o600)
        self.assertEqual(runner.verify_latest("tools/vaultwarden", target, self.root, self.export_root), export)

    def test_open_webui_exports_both_sqlite_databases_without_wal_sidecars(self) -> None:
        data = self.root / "open-webui"
        vector = data / "vector_db"
        vector.mkdir(parents=True)
        for name in ("uploads", "docs", "functions", "tools", "litellm", "cache"):
            (data / name).mkdir()
        target = {
            "engine": "sqlite",
            "database": "open-webui/webui.db",
            "additional_databases": [{"name": "chroma", "database": "open-webui/vector_db/chroma.sqlite3"}],
            "paired_root": "open-webui",
            "paired_files": ["uploads", "docs", "vector_db", "functions", "tools", "litellm", "cache"],
        }
        with (
            contextlib.closing(sqlite3.connect(data / "webui.db")) as webui,
            contextlib.closing(sqlite3.connect(vector / "chroma.sqlite3")) as chroma,
        ):
            for connection in (webui, chroma):
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("CREATE TABLE records (id INTEGER)")
                connection.execute("INSERT INTO records VALUES (1)")
                connection.commit()
            export = open_webui.export("ai/open-webui", target, self.root, self.export_root)
            for connection in (webui, chroma):
                connection.execute("INSERT INTO records VALUES (2)")
                connection.commit()
        self.assertEqual({path.name for path in export.iterdir()}, {"database.sqlite3", "database-chroma.sqlite3", "manifest.json"})
        for filename in ("database.sqlite3", "database-chroma.sqlite3"):
            with contextlib.closing(sqlite3.connect(export / filename)) as restored:
                self.assertEqual(restored.execute("SELECT count(*) FROM records").fetchone(), (1,))
        self.assertEqual(runner.verify_latest("ai/open-webui", target, self.root, self.export_root), export)

    def test_sqlite_export_fails_closed_without_signing_keys(self) -> None:
        data = self.root / "vaultwarden"
        data.mkdir()
        with contextlib.closing(sqlite3.connect(data / "db.sqlite3")) as live:
            live.execute("CREATE TABLE vault (id INTEGER)")
        with self.assertRaisesRegex(BackupError, "signing keys"):
            vaultwarden.export("tools/vaultwarden", {"database": "vaultwarden/db.sqlite3"}, self.root, self.export_root)
        self.assertEqual([path.name for path in (self.export_root / "tools-vaultwarden").iterdir()], [".lock"])

    def test_gitea_export_checks_paired_paths_without_copying_them(self) -> None:
        data = self.root / "gitea"
        (data / "git/repositories").mkdir(parents=True)
        (data / "gitea/conf").mkdir(parents=True)
        (data / "gitea/conf/app.ini").write_text("test config")
        target = {
            "engine": "sqlite",
            "database": "gitea/gitea/gitea.db",
            "paired_root": "gitea",
            "paired_files": ["git/repositories", "gitea/conf/app.ini"],
        }
        with contextlib.closing(sqlite3.connect(data / "gitea/gitea.db")) as live:
            live.execute("CREATE TABLE repositories (id INTEGER)")
        export = sqlite.export("dev/gitea", target, self.root, self.export_root)
        manifest = json.loads((export / "manifest.json").read_text())
        self.assertEqual(manifest["paired_files"], target["paired_files"])
        self.assertEqual({path.name for path in export.iterdir()}, {"database.sqlite3", "manifest.json"})
        self.assertEqual(runner.verify_latest("dev/gitea", target, self.root, self.export_root), export)
        (data / "gitea/conf/app.ini").unlink()
        with self.assertRaisesRegex(BackupError, "Required application files"):
            sqlite.export("dev/gitea", target, self.root, self.export_root)
        self.assertEqual(len([path for path in export.parent.iterdir() if path.is_dir()]), 1)
