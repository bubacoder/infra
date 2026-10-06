"""Native full-storage validation, consistency checks and owned-only cleanup."""

# ruff: noqa: PT009, PT027

import copy
import hashlib
import io
import json
import subprocess
import tarfile
from unittest.mock import patch

from scripts.backup import runner
from scripts.backup.common import BackupError
from scripts.backup.db import qdrant
from tests.backup.support import BackupTestCase

INVENTORY = {
    "server_version": "1.19.1",
    "cluster_status": "disabled",
    "collections": {"snippets": {"points_count": 2, "config": {"params": {"vectors": {"size": 4, "distance": "Cosine"}}}}},
    "aliases": {"search": "snippets"},
}
TARGET = {"version": 1, "engine": "qdrant", "container": "qdrant"}


def tar_bytes(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def full_snapshot(aliases=None, inner=None) -> bytes:
    config = {"collections_mapping": {"snippets": "new.snapshot"}, "collections_aliases": INVENTORY["aliases"] if aliases is None else aliases}
    return tar_bytes(
        {"config.json": json.dumps(config).encode(), "new.snapshot": inner or tar_bytes({"config.json": b"{}", "segment.bin": b"vectors"})}
    )


class FakeAPI:
    def __init__(self):
        self.data = full_snapshot()
        self.created = False
        self.deleted = []
        self.drift = False
        self.download_error = False
        self.cleanup_error = False
        self.cluster_enabled = False
        self.transient_intermediates = False
        self.concurrent_snapshot = False

    def json(self, method, path):
        if method == "DELETE":
            self.deleted.append(path)
            if self.cleanup_error and path.startswith("/snapshots/"):
                raise BackupError("cleanup unavailable")
            return True
        if method == "POST":
            self.created = True
            return {"name": "full-test.snapshot", "size": len(self.data), "checksum": hashlib.sha256(self.data).hexdigest()}
        if path == "/":
            return {"version": "1.19.1"}
        if path == "/cluster":
            return {"status": "enabled" if self.cluster_enabled else "disabled"}
        if path == "/collections":
            return {"collections": [{"name": "snippets"}]}
        if path == "/collections/snippets":
            info = copy.deepcopy(INVENTORY["collections"]["snippets"])
            if self.drift:
                info["points_count"] += 1
            return info
        if path == "/aliases":
            return {"aliases": [{"alias_name": "search", "collection_name": "snippets"}]}
        if path == "/snapshots":
            return [{"name": "operator-full.snapshot"}]
        if path == "/collections/snippets/snapshots":
            names = ["operator.snapshot", "new.snapshot"] if self.created and not self.transient_intermediates else ["operator.snapshot"]
            if self.created and self.concurrent_snapshot:
                names.append("operator-concurrent.snapshot")
            return [{"name": name} for name in names]
        raise AssertionError((method, path))

    def download(self, _path, destination):
        if self.download_error:
            raise BackupError("download failed")
        destination.write_bytes(self.data)
        destination.chmod(0o600)


class QdrantBackupTests(BackupTestCase):
    def test_export_accepts_server_removed_intermediates(self):
        api = FakeAPI()
        api.transient_intermediates = True
        with patch.object(qdrant, "QdrantAPI", return_value=api):
            directory = qdrant.export("ai/qdrant", TARGET, self.root, self.export_root)
        self.assertEqual(runner.verify_latest("ai/qdrant", TARGET, self.root, self.export_root), directory)
        self.assertEqual(api.deleted, ["/snapshots/full-test.snapshot?wait=true"])

    def assert_owned_cleanup(self, api):
        self.assertEqual(api.deleted, ["/snapshots/full-test.snapshot?wait=true", "/collections/snippets/snapshots/new.snapshot?wait=true"])

    def test_concurrent_operator_collection_snapshot_is_not_deleted(self):
        api = FakeAPI()
        api.concurrent_snapshot = True
        with patch.object(qdrant, "QdrantAPI", return_value=api):
            qdrant.export("ai/qdrant", TARGET, self.root, self.export_root)
        self.assert_owned_cleanup(api)

    def test_export_verifies_aliases_nested_payloads_and_preserves_operator_snapshots(self):
        api = FakeAPI()
        with patch.object(qdrant, "QdrantAPI", return_value=api):
            directory = qdrant.export("ai/qdrant", TARGET, self.root, self.export_root)
        self.assert_owned_cleanup(api)
        self.assertEqual(runner.verify_latest("ai/qdrant", TARGET, self.root, self.export_root), directory)
        self.assertEqual({p.name for p in directory.iterdir()}, {"full.snapshot", "inventory.json", "manifest.json"})
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in directory.iterdir()))
        self.assertEqual(json.loads((directory / "inventory.json").read_text()), INVENTORY)

    def test_failed_download_and_checksum_mismatch_cleanup_without_publication(self):
        for failure in ("download", "checksum"):
            api = FakeAPI()
            api.download_error = failure == "download"
            api.transient_intermediates = True
            original = api.download

            def download(path, destination, original=original, failure=failure):
                original(path, destination)
                if failure == "checksum":
                    destination.write_bytes(b"corrupt")

            with (
                patch.object(qdrant, "QdrantAPI", return_value=api),
                patch.object(api, "download", side_effect=download),
                self.assertRaises(BackupError),
            ):
                qdrant.export("ai/qdrant", TARGET, self.root, self.export_root)
            self.assertEqual(api.deleted, ["/snapshots/full-test.snapshot?wait=true"])
            self.assertFalse(any(p.is_dir() for p in (self.export_root / "ai-qdrant").iterdir()))

    def test_inventory_drift_refuses_publication_and_cleans_snapshots(self):
        api = FakeAPI()
        original = api.download

        def download(path, destination):
            original(path, destination)
            api.drift = True

        with (
            patch.object(qdrant, "QdrantAPI", return_value=api),
            patch.object(api, "download", side_effect=download),
            self.assertRaisesRegex(BackupError, "changed during capture"),
        ):
            qdrant.export("ai/qdrant", TARGET, self.root, self.export_root)
        self.assert_owned_cleanup(api)

    def test_cleanup_failure_attempts_all_owned_artifacts_and_refuses_publication(self):
        api = FakeAPI()
        api.cleanup_error = True
        with patch.object(qdrant, "QdrantAPI", return_value=api), self.assertRaisesRegex(BackupError, "refusing publication"):
            qdrant.export("ai/qdrant", TARGET, self.root, self.export_root)
        self.assert_owned_cleanup(api)
        self.assertFalse(any(p.is_dir() for p in (self.export_root / "ai-qdrant").iterdir()))

    def test_distributed_mode_rejected_before_creation(self):
        api = FakeAPI()
        api.cluster_enabled = True
        with patch.object(qdrant, "QdrantAPI", return_value=api), self.assertRaisesRegex(BackupError, "single-node"):
            qdrant.export("ai/qdrant", TARGET, self.root, self.export_root)
        self.assertFalse(api.created)

    def test_native_validation_rejects_alias_loss_traversal_and_broken_nested_archive(self):
        for data in (full_snapshot(aliases={}), full_snapshot(inner=tar_bytes({"../escape": b"data"})), full_snapshot(inner=b"not a tar")):
            path = self.root / "full.snapshot"
            path.write_bytes(data)
            with self.assertRaises(BackupError):
                qdrant.validate_snapshot(path, INVENTORY)

    def test_api_uses_container_address_without_exposing_credentials_in_args(self):
        placeholder = "test-only-key"
        with (
            patch.object(qdrant, "container_environment", return_value=placeholder),
            patch.object(qdrant.shutil, "which", return_value="/usr/bin/docker"),
            patch.object(
                qdrant.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, '{"proxy":{"IPAddress":"172.18.0.4"}}', "")
            ) as commands,
        ):
            api = qdrant.QdrantAPI("qdrant")
        self.assertEqual(api.base, "http://172.18.0.4:6333")
        self.assertNotIn(placeholder, repr(commands.call_args_list))
