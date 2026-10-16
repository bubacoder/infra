"""Unit tests for explicit test-only /etc/hosts cleanup."""

# ruff: noqa: PT009, PT027

import os
import tempfile
import unittest
from pathlib import Path

from scripts.bootstrap.core import BootstrapError
from scripts.bootstrap.hosts import add_temporary_dns_block, remove_temporary_dns_block


class HostsCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.hosts_path = Path(self.tempdir.name) / "hosts"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_hosts(self, content: str) -> None:
        self.hosts_path.write_text(content)
        self.hosts_path.chmod(0o640)

    def test_removes_one_block_and_preserves_unrelated_blocks_and_permissions(self) -> None:
        self.write_hosts(
            "127.0.0.1 localhost\n"
            "# BEGIN infra other temporary DNS\n"
            "192.0.2.2 other.example\n"
            "# END infra other temporary DNS\n"
            "# BEGIN infra docker-host temporary DNS\n"
            "192.0.2.10 home.example\n"
            "# END infra docker-host temporary DNS\n"
            "192.0.2.20 unrelated.example\n"
        )

        remove_temporary_dns_block("docker-host", self.hosts_path)

        self.assertEqual(
            self.hosts_path.read_text(),
            "127.0.0.1 localhost\n"
            "# BEGIN infra other temporary DNS\n"
            "192.0.2.2 other.example\n"
            "# END infra other temporary DNS\n"
            "192.0.2.20 unrelated.example\n",
        )
        self.assertEqual(os.stat(self.hosts_path).st_mode & 0o777, 0o640)

    def test_adds_one_exact_block_and_preserves_permissions(self) -> None:
        self.write_hosts("127.0.0.1 localhost\n")

        add_temporary_dns_block("docker-host", "192.0.2.10", "example.com", self.hosts_path)

        self.assertEqual(
            self.hosts_path.read_text(),
            "127.0.0.1 localhost\n"
            "# BEGIN infra docker-host temporary DNS\n"
            "192.0.2.10 example.com home.example.com traefik.example.com bootstrap-check.example.com\n"
            "# END infra docker-host temporary DNS\n",
        )
        self.assertEqual(os.stat(self.hosts_path).st_mode & 0o777, 0o640)

    def test_add_refuses_existing_or_malformed_block_without_changing_file(self) -> None:
        self.write_hosts("# BEGIN infra docker-host temporary DNS\n")
        original = self.hosts_path.read_bytes()

        with self.assertRaisesRegex(BootstrapError, "already exists or is malformed"):
            add_temporary_dns_block("docker-host", "192.0.2.10", "example.com", self.hosts_path)

        self.assertEqual(self.hosts_path.read_bytes(), original)

    def test_add_refuses_invalid_values_without_changing_file(self) -> None:
        self.write_hosts("127.0.0.1 localhost\n")
        original = self.hosts_path.read_bytes()

        with self.assertRaisesRegex(BootstrapError, "IPv4"):
            add_temporary_dns_block("docker-host", "not-an-address", "example.com", self.hosts_path)
        with self.assertRaisesRegex(BootstrapError, "lowercase DNS"):
            add_temporary_dns_block("docker-host", "192.0.2.10", "Example.com", self.hosts_path)

        self.assertEqual(self.hosts_path.read_bytes(), original)

    def test_refuses_absent_block_without_changing_file(self) -> None:
        self.write_hosts("127.0.0.1 localhost\n")
        original = self.hosts_path.read_bytes()

        with self.assertRaisesRegex(BootstrapError, "exactly one complete"):
            remove_temporary_dns_block("docker-host", self.hosts_path)

        self.assertEqual(self.hosts_path.read_bytes(), original)

    def test_refuses_duplicate_blocks_without_changing_file(self) -> None:
        self.write_hosts(
            "# BEGIN infra docker-host temporary DNS\n"
            "192.0.2.10 home.example\n"
            "# END infra docker-host temporary DNS\n"
            "# BEGIN infra docker-host temporary DNS\n"
            "192.0.2.11 home.example\n"
            "# END infra docker-host temporary DNS\n"
        )
        original = self.hosts_path.read_bytes()

        with self.assertRaisesRegex(BootstrapError, "exactly one complete"):
            remove_temporary_dns_block("docker-host", self.hosts_path)

        self.assertEqual(self.hosts_path.read_bytes(), original)

    def test_refuses_malformed_block_without_changing_file(self) -> None:
        self.write_hosts("# BEGIN infra docker-host temporary DNS\n192.0.2.10 home.example\n# END infra another-host temporary DNS\n")
        original = self.hosts_path.read_bytes()

        with self.assertRaisesRegex(BootstrapError, "exactly one complete"):
            remove_temporary_dns_block("docker-host", self.hosts_path)

        self.assertEqual(self.hosts_path.read_bytes(), original)

    def test_refuses_invalid_name_without_changing_file(self) -> None:
        self.write_hosts("127.0.0.1 localhost\n")
        original = self.hosts_path.read_bytes()

        with self.assertRaisesRegex(BootstrapError, "lowercase hostname label"):
            remove_temporary_dns_block("Docker-host", self.hosts_path)

        self.assertEqual(self.hosts_path.read_bytes(), original)

    def test_adds_newline_only_when_needed(self) -> None:
        for original in (b"", b"127.0.0.1 localhost", b"127.0.0.1 localhost\r\n"):
            with self.subTest(original=original):
                self.hosts_path.write_bytes(original)
                add_temporary_dns_block("docker-host", "192.0.2.10", "example.com", self.hosts_path)
                prefix = original + b"\n" if original and not original.endswith(b"\n") else original
                self.assertEqual(
                    self.hosts_path.read_bytes(),
                    prefix + b"# BEGIN infra docker-host temporary DNS\n"
                    b"192.0.2.10 example.com home.example.com traefik.example.com bootstrap-check.example.com\n"
                    b"# END infra docker-host temporary DNS\n",
                )

    def test_removes_crlf_block_preserving_unrelated_bytes(self) -> None:
        original = b"127.0.0.1 localhost\r\n\xff unrelated host without final newline"
        self.hosts_path.write_bytes(
            b"127.0.0.1 localhost\r\n"
            b"# BEGIN infra docker-host temporary DNS\r\n"
            b"192.0.2.10 home.example\r\n"
            b"# END infra docker-host temporary DNS\r\n"
            b"\xff unrelated host without final newline"
        )

        remove_temporary_dns_block("docker-host", self.hosts_path)

        self.assertEqual(self.hosts_path.read_bytes(), original)

    def test_refuses_reversed_or_nested_markers_without_changing_file(self) -> None:
        for content in (
            "# END infra docker-host temporary DNS\n# BEGIN infra docker-host temporary DNS\n",
            "# BEGIN infra docker-host temporary DNS\n# BEGIN infra other temporary DNS\n# END infra docker-host temporary DNS\n",
            "# BEGIN infra docker-host temporary DNS\n# END infra other temporary DNS\n# END infra docker-host temporary DNS\n",
        ):
            with self.subTest(content=content):
                self.write_hosts(content)
                with self.assertRaisesRegex(BootstrapError, "Malformed temporary DNS block"):
                    remove_temporary_dns_block("docker-host", self.hosts_path)
                self.assertEqual(self.hosts_path.read_bytes(), content.encode())

    def test_add_refuses_end_only_crlf_marker_without_changing_file(self) -> None:
        original = b"# END infra docker-host temporary DNS\r\n"
        self.hosts_path.write_bytes(original)

        with self.assertRaisesRegex(BootstrapError, "already exists or is malformed"):
            add_temporary_dns_block("docker-host", "192.0.2.10", "example.com", self.hosts_path)

        self.assertEqual(self.hosts_path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
