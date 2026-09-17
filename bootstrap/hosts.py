"""Explicit removal of a test-only bootstrap /etc/hosts block."""

import argparse
import os
import re
import stat
import tempfile
from pathlib import Path

from .core import BootstrapError

HOSTNAME_LABEL = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def marker(name: str, boundary: str) -> bytes:
    return f"# {boundary} infra {name} temporary DNS".encode()


def validate_name(name: str) -> None:
    if not HOSTNAME_LABEL.fullmatch(name):
        raise BootstrapError("NAME must be a lowercase hostname label")


def remove_temporary_dns_block(name: str, hosts_path: Path = Path("/etc/hosts")) -> None:
    """Atomically remove one complete, exact test-only hosts block."""
    validate_name(name)
    content = hosts_path.read_bytes()
    lines = content.splitlines(keepends=True)
    begin = marker(name, "BEGIN")
    end = marker(name, "END")
    starts = [index for index, line in enumerate(lines) if line.rstrip(b"\r\n") == begin]
    ends = [index for index, line in enumerate(lines) if line.rstrip(b"\r\n") == end]

    if len(starts) != 1 or len(ends) != 1:
        raise BootstrapError(f"Expected exactly one complete temporary DNS block for {name}")

    start, finish = starts[0], ends[0]
    if finish <= start:
        raise BootstrapError(f"Malformed temporary DNS block for {name}")

    for line in lines[start + 1 : finish]:
        stripped = line.rstrip(b"\r\n")
        if stripped.startswith(b"# BEGIN infra ") or stripped.startswith(b"# END infra "):
            raise BootstrapError(f"Malformed temporary DNS block for {name}")

    replacement = b"".join([*lines[:start], *lines[finish + 1 :]])
    file_mode = stat.S_IMODE(hosts_path.stat().st_mode)
    with tempfile.NamedTemporaryFile(dir=hosts_path.parent, delete=False) as temporary:
        temporary.write(replacement)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    try:
        os.chmod(temporary_path, file_mode)
        os.replace(temporary_path, hosts_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Lowercase VM hostname label")
    parser.add_argument("--hosts-path", type=Path, default=Path("/etc/hosts"), help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if os.geteuid() != 0:
        raise BootstrapError("Temporary DNS cleanup must run as root")
    remove_temporary_dns_block(args.name, args.hosts_path)


if __name__ == "__main__":
    try:
        main()
    except BootstrapError as error:
        raise SystemExit(f"Error: {error}") from error
