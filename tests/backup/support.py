"""Temporary host-volume fixture shared by backup tests."""

import tempfile
import unittest
from pathlib import Path


class BackupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name) / "volumes"
        self.root.mkdir()
        self.export_root = Path(self.tempdir.name) / "db-backups"

    def tearDown(self) -> None:
        self.tempdir.cleanup()
