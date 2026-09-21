"""Explicit management of test-only bootstrap /etc/hosts blocks."""

import argparse
import ipaddress
import os
import re
import stat
import tempfile
from pathlib import Path

from .core import BootstrapError

HOSTNAME_LABEL = re.compile(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
DOMAIN = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z")


def marker(name: str, boundary: str) -> bytes:
    return f"# {boundary} infra {name} temporary DNS".encode()


def validate_name(name: str) -> None:
    if not HOSTNAME_LABEL.fullmatch(name):
        raise BootstrapError("NAME must be a lowercase hostname label")


def validate_address(address: str) -> None:
    try:
        ipaddress.IPv4Address(address)
    except ipaddress.AddressValueError as error:
        raise BootstrapError("ADDRESS must be an IPv4 address") from error


def validate_domain(domain: str) -> None:
    if not DOMAIN.fullmatch(domain):
        raise BootstrapError("DOMAIN must be a lowercase DNS domain")


def replace_hosts_content(hosts_path: Path, content: bytes) -> None:
    file_mode = stat.S_IMODE(hosts_path.stat().st_mode)
    with tempfile.NamedTemporaryFile(dir=hosts_path.parent, delete=False) as temporary:
        temporary.write(content)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    try:
        os.chmod(temporary_path, file_mode)
        os.replace(temporary_path, hosts_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def add_temporary_dns_block(name: str, address: str, domain: str, hosts_path: Path = Path("/etc/hosts")) -> None:
    """Atomically add one exact test-only hosts block when it is absent."""
    validate_name(name)
    validate_address(address)
    validate_domain(domain)
    content = hosts_path.read_bytes()
    begin, end = marker(name, "BEGIN"), marker(name, "END")
    lines = content.splitlines(keepends=True)
    if any(line.rstrip(b"\r\n") in {begin, end} for line in lines):
        raise BootstrapError(f"Temporary DNS block for {name} already exists or is malformed")
    if content and not content.endswith(b"\n"):
        content += b"\n"
    names = f"{domain} home.{domain} traefik.{domain} bootstrap-check.{domain}"
    block = b"\n".join((begin, f"{address} {names}".encode(), end)) + b"\n"
    replace_hosts_content(hosts_path, content + block)


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
    replace_hosts_content(hosts_path, replacement)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Lowercase VM hostname label")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--add", action="store_true", help="Add a temporary DNS block")
    action.add_argument("--remove", action="store_true", help="Remove a temporary DNS block")
    parser.add_argument("--address", help="IPv4 address for --add")
    parser.add_argument("--domain", help="Base DNS domain for --add")
    parser.add_argument("--hosts-path", type=Path, default=Path("/etc/hosts"), help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if os.geteuid() != 0:
        raise BootstrapError("Temporary DNS updates must run as root")
    if args.add:
        if not args.address or not args.domain:
            raise BootstrapError("ADDRESS and DOMAIN are required with --add")
        add_temporary_dns_block(args.name, args.address, args.domain, args.hosts_path)
    else:
        remove_temporary_dns_block(args.name, args.hosts_path)


if __name__ == "__main__":
    try:
        main()
    except BootstrapError as error:
        raise SystemExit(f"Error: {error}") from error
