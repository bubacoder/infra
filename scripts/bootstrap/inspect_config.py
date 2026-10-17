"""Offline, allowlisted configuration display for operators and AI agents."""

from pathlib import Path
from urllib.parse import urlparse

import yaml

from .config import read_document
from .core import ROOT, ConfigError

SECRET = object()
# Deliberately independent of dataclass serialization: new fields are hidden
# until explicitly reviewed here. Never dump raw YAML, unknown keys or mappings
# found where scalar settings are expected.
DISPLAY_FIELDS = {
    "version": None,
    "target": None,
    "repository": {"url": None, "branch": None},
    "deployment": {"admin_model": None, "services": [None]},
    "proxmox": {"ssh_target": None},
    "vm": dict.fromkeys(
        (
            "id",
            "name",
            "ubuntu_version",
            "username",
            "cpu_cores",
            "memory_max_mib",
            "memory_min_mib",
            "disk_size",
            "storage",
            "bridge",
            "mac",
            "ssh_public_key",
        )
    ),
    "aws": dict.fromkeys(
        (
            "account_id",
            "region",
            "profile",
            "ubuntu_version",
            "architecture",
            "instance_type",
            "admin_source_cidr",
            "os_disk_size_gb",
            "data_disk_size_gb",
        )
    ),
    "network": {
        "expected_ipv4": None,
        "domain": None,
        "dns": {
            "enabled": None,
            "mode": None,
            "verify": None,
            "cloudflare": {"zone": None},
            "adguard": {"url": None, "username": None, "password": SECRET},
        },
    },
    "host": {"docker_volumes": None, "timezone": None},
    "tls": {"provider": None, "acme_email": None, "token": SECRET},
}


def public_scalar(value: object) -> object:
    """Show only primitive metadata; reject URLs that could carry credentials."""
    if isinstance(value, str):
        if "://" in value:
            try:
                parsed = urlparse(value)
                if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
                    return "<redacted>"
            except ValueError:
                return "<redacted>"
        return value
    if value is None or type(value) in (int, float, bool):
        return value
    return "<invalid setting type>"


def project(value: object, schema: object, secrets: list[str]) -> object:
    """Build new public data; never reuse untrusted nested containers."""
    if schema is SECRET:
        if isinstance(value, (str, int, float)) and not isinstance(value, bool) and str(value):
            secrets.append(str(value))
        return "<redacted>"
    if isinstance(schema, dict):
        if not isinstance(value, dict):
            return "<invalid setting type>"
        return {key: project(value[key], child, secrets) for key, child in schema.items() if key in value}
    if isinstance(schema, list):
        return [public_scalar(item) for item in value] if isinstance(value, list) else "<invalid setting type>"
    return public_scalar(value)


def scrub(value: object, secrets: list[str]) -> object:
    """Also hide known secret values accidentally repeated in public fields."""
    if isinstance(value, dict):
        return {key: scrub(child, secrets) for key, child in value.items()}
    if isinstance(value, list):
        return [scrub(child, secrets) for child in value]
    if value == "<redacted>":
        return value
    if isinstance(value, str):
        for secret in sorted(set(secrets), key=len, reverse=True):
            value = value.replace(secret, "<redacted>")
    elif value is not None and str(value) in secrets:
        return "<redacted>"
    return value


def show(path: Path, root: Path = ROOT) -> None:
    """Print configured public settings without schema validation or side effects."""
    _, raw = read_document(path, root)
    if not isinstance(raw, dict):
        raise ConfigError("Bootstrap configuration must be a YAML mapping")
    secrets: list[str] = []
    public = project(raw, DISPLAY_FIELDS, secrets)
    print(yaml.safe_dump(scrub(public, secrets), sort_keys=False).rstrip())
