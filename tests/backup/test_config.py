"""Reject unsafe service definitions and load ignored host paths without execution."""

# ruff: noqa: PT009, PT027

from scripts.backup import config
from scripts.backup.apps import open_webui
from scripts.backup.common import BackupError
from tests.backup.support import BackupTestCase


class BackupConfigTests(BackupTestCase):
    def definition(self, service: str, text: str):
        path = self.root / service / "backup.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_sections_reject_old_mixed_or_misplaced_configuration(self) -> None:
        invalid = [
            {"version": 1, "engine": "sqlite", "database": "vaultwarden/db.sqlite3"},
            {"version": 1},
            {"version": 1.0, "files": {"ignore": []}},
            {"version": 2, "files": {"ignore": []}},
            {"version": 1, "databases": []},
            {"version": 1, "databases": {"database": "vaultwarden/db.sqlite3"}},
            {"version": 1, "files": {"ignore": []}, "kopia": {"ignore": []}},
            {"version": 1, "databases": {"engine": "sqlite", "database": "vaultwarden/db.sqlite3", "paired_root": "vaultwarden"}},
            {"version": 1, "files": {"root": "vaultwarden"}},
            {"version": 1, "files": {"required": ["attachments"]}},
            {"version": 1, "files": {"root": "vaultwarden", "required": ["../other-service"]}},
            {"version": 1, "files": {"required_files": ["data/configuration.yaml"]}},
        ]
        for target in invalid:
            path = self.definition("tools/vaultwarden", config.yaml.safe_dump(target))
            with self.subTest(target=target), self.assertRaises(BackupError):
                config.load_definition(path)

    def test_homeassistant_archive_requirements_remain_export_settings(self) -> None:
        requirements = ["data/configuration.yaml", "data/.storage/auth", "data/home-assistant_v2.db"]
        target = {
            "version": 1,
            "databases": {
                "engine": "homeassistant",
                "container": "homeassistant",
                "data": "homeassistant",
                "token_file": "homeassistant/backup-token",
                "required_files": requirements,
            },
            "files": {"ignore": ["/homeassistant/home-assistant.log*"]},
        }
        self.definition("automation/homeassistant", config.yaml.safe_dump(target))
        normalized = config.load_target("automation/homeassistant", self.root)
        self.assertEqual(normalized["required_files"], requirements)
        self.assertNotIn("paired_files", normalized)
        self.assertNotIn("ignore", normalized)

    def test_file_requirements_normalize_without_entering_artifact_schema(self) -> None:
        definition = {
            "version": 1,
            "databases": {"engine": "postgresql", "container": "postgresql", "user": "postgres", "all_databases": True},
            "files": {"root": "mattermost", "required": ["config", "data"], "ignore": ["/postgresql/data"]},
        }
        self.definition("database/postgresql", config.yaml.safe_dump(definition))
        self.assertEqual(
            config.load_target("database/postgresql", self.root),
            {
                "version": 1,
                "engine": "postgresql",
                "container": "postgresql",
                "user": "postgres",
                "all_databases": True,
                "paired_root": "mattermost",
                "paired_files": ["config", "data"],
            },
        )

    def test_target_rejects_unknown_fields_and_path_traversal(self) -> None:
        path = self.definition(
            "security/authentik",
            "version: 1\ndatabases:\n  engine: postgresql\n  container: authentik-postgresql\n  database: authentik\n  user: authentik\n",
        )
        self.assertEqual(config.load_target("security/authentik", self.root)["database"], "authentik")
        with self.assertRaises(BackupError):
            config.load_target("security/../authentik", self.root)
        path.write_text(path.read_text() + "password: exposed\n")
        with self.assertRaises(BackupError):
            config.load_target("security/authentik", self.root)

    def test_sqlite_target_rejects_other_service_paths(self) -> None:
        path = self.definition("tools/vaultwarden", "version: 1\ndatabases:\n  engine: sqlite\n  database: vaultwarden/db.sqlite3\n")
        self.assertEqual(config.load_target("tools/vaultwarden", self.root)["database"], "vaultwarden/db.sqlite3")
        path.write_text("version: 1\ndatabases:\n  engine: sqlite\n  database: ../authentik/postgresql\n")
        with self.assertRaises(BackupError):
            config.load_target("tools/vaultwarden", self.root)

    def test_gitea_target_requires_its_own_database_and_paired_paths(self) -> None:
        path = self.definition(
            "dev/gitea",
            "version: 1\ndatabases:\n  engine: sqlite\n  database: gitea/gitea/gitea.db\nfiles:\n  root: gitea\n  required:\n    - git/repositories\n    - gitea/conf/app.ini\n",
        )
        self.assertEqual(config.load_target("dev/gitea", self.root)["paired_root"], "gitea")
        path.write_text(path.read_text().replace("git/repositories", "../vaultwarden/db.sqlite3"))
        with self.assertRaises(BackupError):
            config.load_target("dev/gitea", self.root)

    def test_open_webui_target_rejects_other_app_or_duplicate_sqlite_databases(self) -> None:
        text = (
            "version: 1\ndatabases:\n  engine: sqlite\n  database: open-webui/webui.db\n  additional_databases:\n"
            "    - name: chroma\n      database: open-webui/vector_db/chroma.sqlite3\nfiles:\n  root: open-webui\n  required:\n    - uploads\n"
        )
        path = self.definition("ai/open-webui", text)
        self.assertEqual(config.load_target("ai/open-webui", self.root)["additional_databases"][0]["name"], "chroma")
        path.write_text(text.replace("open-webui/vector_db/chroma.sqlite3", "../vaultwarden/db.sqlite3"))
        with self.assertRaises(BackupError):
            config.load_target("ai/open-webui", self.root)
        path.write_text(text.replace("files:\n", "    - name: chroma\n      database: open-webui/duplicate.db\nfiles:\n"))
        with self.assertRaises(BackupError):
            config.load_target("ai/open-webui", self.root)

    def test_shared_postgresql_target_requires_all_databases(self) -> None:
        path = self.definition(
            "database/postgresql",
            "version: 1\ndatabases:\n  engine: postgresql\n  container: postgresql\n  user: postgres\n  all_databases: true\nfiles:\n  root: mattermost\n  required:\n    - data\n",
        )
        self.assertTrue(config.load_target("database/postgresql", self.root)["all_databases"])
        path.write_text(path.read_text().replace("all_databases: true", "all_databases: false"))
        with self.assertRaises(BackupError):
            config.load_target("database/postgresql", self.root)

    def test_wg_easy_storage_alias_does_not_allow_other_service_roots(self) -> None:
        text = (
            "version: 1\ndatabases:\n  engine: sqlite\n  storage_root: wg-easy-v15\n  database: wg-easy-v15/wg-easy.db\n"
            "files:\n  root: wg-easy-v15\n  required:\n    - wg0.conf\n"
        )
        path = self.definition("security/wg-easy", text)
        self.assertEqual(config.load_target("security/wg-easy", self.root)["paired_root"], "wg-easy-v15")
        path.write_text(text.replace("wg-easy-v15", "vaultwarden"))
        with self.assertRaises(BackupError):
            config.load_target("security/wg-easy", self.root)

    def test_offline_model_must_be_pinned_and_explicitly_paired(self) -> None:
        target = {
            "version": 1,
            "databases": {"engine": "sqlite", "database": "open-webui/webui.db"},
            "files": {"root": "open-webui", "required": ["uploads"], "offline_model": {"model": open_webui.MODEL, "revision": "a" * 40}},
        }
        path = self.definition("ai/open-webui", config.yaml.safe_dump(target))
        with self.assertRaises(BackupError):
            config.load_target("ai/open-webui", self.root)
        target["files"]["required"].extend(open_webui.model_paths(target["files"]["offline_model"]))
        path.write_text(config.yaml.safe_dump(target))
        self.assertEqual(config.load_target("ai/open-webui", self.root)["offline_model"], target["files"]["offline_model"])

    def test_n8n_target_accepts_dedicated_database_and_paired_files(self) -> None:
        path = self.definition(
            "automation/n8n",
            "version: 1\ndatabases:\n  engine: postgresql\n  container: n8n-postgres\n  database: n8n\n  user: root\nfiles:\n  root: n8n\n  required:\n    - config\n    - binaryData\n",
        )
        self.assertEqual(config.load_target("automation/n8n", self.root)["paired_files"], ["config", "binaryData"])
        path.write_text(path.read_text().replace("binaryData", "../vaultwarden"))
        with self.assertRaises(BackupError):
            config.load_target("automation/n8n", self.root)

    def test_guacamole_target_keeps_embedded_pg_separate_from_shared_server(self) -> None:
        self.definition(
            "tools/guacamole",
            "version: 1\ndatabases:\n  engine: postgresql\n  container: guacamole\n  database: guacamole_db\n  user: guacamole\nfiles:\n  root: guacamole\n  required:\n    - guacamole/guacamole.properties\n",
        )
        target = config.load_target("tools/guacamole", self.root)
        self.assertEqual((target["container"], target["database"]), ("guacamole", "guacamole_db"))
        self.assertIn("tools/guacamole", config.BACKUP_SERVICES)

    def test_mongodb_target_rejects_unrelated_paired_paths(self) -> None:
        path = self.definition(
            "database/mongodb",
            "version: 1\ndatabases:\n  engine: mongodb\n  container: mongodb\n  writer: unifi-network-application\nfiles:\n  root: unifi-network-application\n  required:\n    - data\n",
        )
        self.assertEqual(config.load_target("database/mongodb", self.root)["writer"], "unifi-network-application")
        path.write_text(path.read_text().replace("  - data", "  - ../n8n/config"))
        with self.assertRaises(BackupError):
            config.load_target("database/mongodb", self.root)

    def test_couchdb_target_requires_local_data_and_config(self) -> None:
        path = self.definition(
            "database/couchdb", "version: 1\ndatabases:\n  engine: couchdb\n  container: couchdb\n  data: couchdb/data\n  config: couchdb/etc\n"
        )
        self.assertEqual(config.load_target("database/couchdb", self.root)["data"], "couchdb/data")
        path.write_text(path.read_text().replace("couchdb/data", "../vaultwarden"))
        with self.assertRaises(BackupError):
            config.load_target("database/couchdb", self.root)

    def test_qdrant_target_is_full_storage_and_restricted_to_homelab_container(self) -> None:
        path = self.definition("ai/qdrant", "version: 1\ndatabases:\n  engine: qdrant\n  container: qdrant\n")
        self.assertEqual(config.load_target("ai/qdrant", self.root)["engine"], "qdrant")
        self.assertIn("ai/qdrant", config.BACKUP_SERVICES)
        path.write_text(path.read_text().replace("container: qdrant", "container: other-qdrant"))
        with self.assertRaises(BackupError):
            config.load_target("ai/qdrant", self.root)

    def test_docker_volumes_uses_host_override_without_running_dotenv(self) -> None:
        directory = self.root / "config"
        (directory / "myhost").mkdir(parents=True)
        (directory / ".env").write_text("DOCKER_VOLUMES=/not/the/host\n")
        (directory / "myhost/.env").write_text(f"DOCKER_VOLUMES={self.root}\n")
        self.assertEqual(config.docker_volumes("myhost", directory), self.root)

    def test_backup_root_is_explicit_independent_and_host_overridden(self) -> None:
        directory = self.root / "config"
        (directory / "myhost").mkdir(parents=True)
        self.export_root.mkdir()
        (directory / ".env").write_text("DB_BACKUP_ROOT=/missing\n")
        (directory / "myhost/.env").write_text(f"DB_BACKUP_ROOT={self.export_root}\n")
        self.assertEqual(config.backup_root("myhost", self.root, directory), self.export_root)
        for value in (str(self.root), str(self.root / "config"), "${DOCKER_VOLUMES}/db-backups", "relative"):
            (directory / "myhost/.env").write_text(f"DB_BACKUP_ROOT={value}\n")
            with self.assertRaises(BackupError):
                config.backup_root("myhost", self.root, directory)
        (directory / ".env").write_text("")
        (directory / "myhost/.env").write_text("")
        with self.assertRaises(BackupError):
            config.backup_root("myhost", self.root, directory)
