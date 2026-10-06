"""Model archives must survive cache loss and reject incomplete or unsafe artifacts."""

# ruff: noqa: PT009, PT027

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.backup.apps import open_webui as backup_models


class ModelArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = {"model": backup_models.MODEL, "revision": "a" * 40}
        self.cache = self.root / "cache/embedding/models/models--sentence-transformers--all-MiniLM-L6-v2"
        source = self.cache / "snapshots" / self.config["revision"]
        (self.cache / "refs").mkdir(parents=True)
        (self.cache / "refs/main").write_text(self.config["revision"])
        for name in backup_models.MODEL_FILES:
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture " + name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_published_archive_is_reused_and_independent_of_cache(self) -> None:
        manifest = backup_models.ensure_model(self.root, self.config)
        archive = self.root / backup_models.model_paths(self.config)[0]
        before = archive.stat().st_mtime_ns
        self.assertEqual(backup_models.ensure_model(self.root, self.config), manifest)
        self.assertEqual(archive.stat().st_mtime_ns, before)
        shutil.rmtree(self.cache)
        self.assertEqual(backup_models.verify_model(self.root, self.config), manifest)

    def test_cache_symlink_escape_never_publishes_an_archive(self) -> None:
        path = self.cache / "snapshots" / self.config["revision"] / "model.safetensors"
        path.unlink()
        outside = self.root / "unrelated-secret"
        outside.write_text("not a model")
        path.symlink_to(outside)
        with self.assertRaises(backup_models.ModelArchiveError):
            backup_models.ensure_model(self.root, self.config)
        self.assertFalse((self.root / backup_models.model_paths(self.config)[0]).exists())

    def test_changed_revision_or_corrupt_archive_fails_closed(self) -> None:
        backup_models.ensure_model(self.root, self.config)
        archive = self.root / backup_models.model_paths(self.config)[0]
        archive.write_bytes(b"corrupt")
        with self.assertRaises(backup_models.ModelArchiveError):
            backup_models.ensure_model(self.root, self.config)
        (self.cache / "refs/main").write_text("b" * 40)
        with self.assertRaises(backup_models.ModelArchiveError):
            backup_models.ensure_model(self.root, self.config)

    def test_rebuild_is_deterministic(self) -> None:
        first = backup_models.ensure_model(self.root, self.config)
        destination = (self.root / backup_models.model_paths(self.config)[0]).parent
        shutil.rmtree(destination)
        second = backup_models.ensure_model(self.root, self.config)
        self.assertEqual(first["archive_sha256"], second["archive_sha256"])
        self.assertEqual(first["files"], second["files"])

    def test_missing_member_inventory_is_rejected(self) -> None:
        backup_models.ensure_model(self.root, self.config)
        path = self.root / backup_models.model_paths(self.config)[1]
        manifest = json.loads(path.read_text())
        manifest["files"].pop()
        path.write_text(json.dumps(manifest))
        with self.assertRaises(backup_models.ModelArchiveError):
            backup_models.verify_model(self.root, self.config)

    def test_retention_preserves_revisions_referenced_by_retained_databases(self) -> None:
        configs = []
        for character in "abcde":
            config = {"model": backup_models.MODEL, "revision": character * 40}
            source = self.cache / "snapshots" / config["revision"]
            if not source.exists():
                shutil.copytree(self.cache / "snapshots" / self.config["revision"], source)
            (self.cache / "refs/main").write_text(config["revision"])
            backup_models.ensure_model(self.root, config)
            configs.append(config)
        protected = {configs[0]["revision"], configs[-1]["revision"]}
        removed = backup_models.prune_models(self.root, protected)
        self.assertEqual(removed, [configs[1]["revision"]])
        self.assertTrue((self.root / backup_models.model_paths(configs[0])[0]).exists())
