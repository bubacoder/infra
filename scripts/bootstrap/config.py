"""Bootstrap configuration and repository revision validation."""

import ipaddress
import re
import stat
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ModuleNotFoundError:
    print("Error: 'yaml' module not found. Install it with: pip3 install pyyaml", file=sys.stderr)
    sys.exit(1)

from .core import (
    ROOT,
    SUPPORTED_SERVICES,
    BootstrapConfig,
    BootstrapError,
    ConfigError,
    DeploymentConfig,
    DnsConfig,
    HostConfig,
    NetworkConfig,
    ProxmoxConfig,
    RepositoryConfig,
    Runner,
    TlsConfig,
    VmConfig,
)

NAME_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
MAC_PATTERN = re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")
SHELL_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_.:/@+-]+")


def require_mapping(value: object, field: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    """Return a mapping whose string keys satisfy the allowed and required sets."""
    if not isinstance(value, dict):
        raise ConfigError(f"{field} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise ConfigError(f"{field} field names must be strings")
    unknown, missing = set(value) - allowed, required - set(value)
    if unknown:
        raise ConfigError(f"{field} contains unknown fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ConfigError(f"{field} is missing fields: {', '.join(sorted(missing))}")
    return value


def require_string(value: object, field: str) -> str:
    """Return a stripped, nonempty single-line string."""
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        raise ConfigError(f"{field} must be a non-empty string")
    return value.strip()


def require_positive_int(value: object, field: str) -> int:
    """Return a positive integer, rejecting booleans."""
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ConfigError(f"{field} must be a positive integer")
    return value


def require_shell_token(value: object, field: str) -> str:
    """Return a nonempty string containing only supported shell-token characters."""
    token = require_string(value, field)
    if not SHELL_TOKEN_PATTERN.fullmatch(token):
        raise ConfigError(f"{field} contains unsupported characters")
    return token


def validate_file_security(path: Path, root: Path) -> Path:
    """Resolve a private bootstrap configuration path located under root/config."""
    resolved, config_dir = path.expanduser().resolve(), (root / "config").resolve()
    if not resolved.is_relative_to(config_dir):
        raise ConfigError(f"Bootstrap configuration must be stored under {config_dir}")
    try:
        mode = stat.S_IMODE(resolved.stat().st_mode)
    except OSError as error:
        raise ConfigError(f"Cannot read bootstrap configuration {resolved}: {error}") from error
    if mode & 0o077:
        raise ConfigError(f"Bootstrap configuration must not be accessible by group or others: chmod 600 {resolved}")
    return resolved


def validate_name(value: object, field: str) -> str:
    """Return a value normalized as a lowercase hostname label."""
    name = require_string(value, field).lower()
    if not NAME_PATTERN.fullmatch(name):
        raise ConfigError(f"{field} must be a valid lowercase hostname label")
    return name


def validate_mac(value: object, field: str = "vm.mac") -> str:
    """Return an uppercase, colon-separated unicast MAC address."""
    mac = require_string(value, field).upper()
    if not MAC_PATTERN.fullmatch(mac):
        raise ConfigError(f"{field} must be a colon-separated MAC address")
    if int(mac[:2], 16) & 1:
        raise ConfigError(f"{field} must be a unicast MAC address")
    return mac


def validate_domain(value: object) -> str:
    """Return a lowercase domain name without a trailing dot."""
    domain = require_string(value, "network.domain").lower().rstrip(".")
    if len(domain.split(".")) < 2 or any(not NAME_PATTERN.fullmatch(label) for label in domain.split(".")):
        raise ConfigError("network.domain must be a valid domain name")
    return domain


def validate_repository_url(url: str) -> None:
    """Reject repository URLs containing credentials or unsafe argument syntax."""
    if url.startswith("-"):
        raise ConfigError("repository.url is invalid")
    parsed = urlparse(url)
    if parsed.password or parsed.query or parsed.fragment or (parsed.scheme in {"http", "https"} and parsed.username):
        raise ConfigError("repository.url must not contain credentials")


def validate_repository_input(value: object) -> dict[str, str] | None:
    """Validate an optional repository override and return its normalized fields."""
    if value is None:
        return None
    repository = require_mapping(value, "repository", {"url", "branch"}, {"url", "branch"})
    url, branch = require_string(repository["url"], "repository.url"), require_string(repository["branch"], "repository.branch")
    validate_repository_url(url)
    if branch.startswith("-") or any(character.isspace() for character in branch):
        raise ConfigError("repository.branch is invalid")
    return {"url": url, "branch": branch}


def load_config(path: Path, root: Path = ROOT) -> BootstrapConfig:  # noqa: PLR0912
    """Load and validate a version 1 bootstrap YAML document."""
    source = validate_file_security(path, root)
    try:
        raw = yaml.safe_load(source.read_text())
    except yaml.YAMLError as error:
        location = f" at line {error.problem_mark.line + 1}, column {error.problem_mark.column + 1}" if error.problem_mark else ""
        raise ConfigError(f"Cannot parse bootstrap configuration{location}") from error
    except OSError as error:
        raise ConfigError(f"Cannot read bootstrap configuration: {error.strerror or 'I/O error'}") from error
    document = require_mapping(
        raw,
        "bootstrap configuration",
        {"version", "repository", "deployment", "proxmox", "vm", "network", "host", "tls"},
        {"version", "deployment", "proxmox", "vm", "network", "host", "tls"},
    )
    if document["version"] != 1:
        raise ConfigError("version must be 1")
    deployment = require_mapping(document["deployment"], "deployment", {"admin_model", "services"}, {"admin_model", "services"})
    if require_string(deployment["admin_model"], "deployment.admin_model") != "separate":
        raise ConfigError("deployment.admin_model currently supports only 'separate'")
    if not isinstance(deployment["services"], list) or any(not isinstance(service, str) for service in deployment["services"]):
        raise ConfigError("deployment.services must be a list of service paths")
    services = tuple(deployment["services"])
    if services != SUPPORTED_SERVICES:
        raise ConfigError(f"deployment.services currently must be: {', '.join(SUPPORTED_SERVICES)}")
    proxmox = require_mapping(document["proxmox"], "proxmox", {"ssh_target"}, {"ssh_target"})
    ssh_target = require_shell_token(proxmox["ssh_target"], "proxmox.ssh_target")
    if ssh_target.startswith("-"):
        raise ConfigError("proxmox.ssh_target is invalid")
    vm = require_mapping(
        document["vm"],
        "vm",
        {
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
        },
        {
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
            "ssh_public_key",
        },
    )
    vm_id = vm["id"]
    if vm_id != "auto" and (not isinstance(vm_id, int) or isinstance(vm_id, bool) or vm_id <= 0):
        raise ConfigError("vm.id must be a positive integer or 'auto'")
    memory_min, memory_max = (
        require_positive_int(vm["memory_min_mib"], "vm.memory_min_mib"),
        require_positive_int(vm["memory_max_mib"], "vm.memory_max_mib"),
    )
    if memory_min > memory_max:
        raise ConfigError("vm.memory_min_mib must not exceed vm.memory_max_mib")
    public_key = Path(require_string(vm["ssh_public_key"], "vm.ssh_public_key")).expanduser().resolve()
    try:
        public_key_content = public_key.read_text().strip()
    except OSError as error:
        raise ConfigError(f"Cannot read vm.ssh_public_key: {error.strerror or 'I/O error'}") from error
    if not public_key.is_file() or not public_key_content.startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-")):
        raise ConfigError(f"vm.ssh_public_key is not a usable public key: {public_key}")
    network = require_mapping(document["network"], "network", {"expected_ipv4", "domain", "dns"}, {"expected_ipv4", "domain", "dns"})
    expected_value = require_string(network["expected_ipv4"], "network.expected_ipv4")
    try:
        expected_ipv4 = None if expected_value == "auto" else str(ipaddress.IPv4Address(expected_value))
    except ipaddress.AddressValueError as error:
        raise ConfigError("network.expected_ipv4 must be an IPv4 address or 'auto'") from error
    dns = require_mapping(network["dns"], "network.dns", {"mode", "verify"}, {"mode", "verify"})
    if dns["mode"] != "external" or dns["verify"] is not True:
        raise ConfigError("network.dns currently requires mode: external and verify: true")
    host = require_mapping(document["host"], "host", {"docker_volumes", "timezone"}, {"docker_volumes", "timezone"})
    docker_volumes = require_shell_token(host["docker_volumes"], "host.docker_volumes")
    if not Path(docker_volumes).is_absolute():
        raise ConfigError("host.docker_volumes must be an absolute path")
    tls = require_mapping(document["tls"], "tls", {"provider", "acme_email", "token"}, {"provider", "acme_email", "token"})
    if tls["provider"] != "cloudflare":
        raise ConfigError("tls.provider currently supports only 'cloudflare'")
    email, token = require_string(tls["acme_email"], "tls.acme_email"), require_string(tls["token"], "tls.token")
    if "@" not in email:
        raise ConfigError("tls.acme_email must be an email address")
    if token.startswith(("<", "replace-")):
        raise ConfigError("tls.token still contains a placeholder")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        raise ConfigError("tls.token contains unsupported characters")
    return BootstrapConfig(
        source,
        validate_repository_input(document.get("repository")),
        DeploymentConfig("separate", services),
        ProxmoxConfig(ssh_target),
        VmConfig(
            vm_id,
            validate_name(vm["name"], "vm.name"),
            require_shell_token(vm["ubuntu_version"], "vm.ubuntu_version"),
            validate_name(vm["username"], "vm.username"),
            require_positive_int(vm["cpu_cores"], "vm.cpu_cores"),
            memory_max,
            memory_min,
            require_shell_token(vm["disk_size"], "vm.disk_size"),
            require_shell_token(vm["storage"], "vm.storage"),
            require_shell_token(vm["bridge"], "vm.bridge"),
            validate_mac(vm["mac"]) if vm.get("mac") else None,
            public_key,
        ),
        NetworkConfig(expected_ipv4, validate_domain(network["domain"]), DnsConfig("external", True)),
        HostConfig(docker_volumes, require_shell_token(host["timezone"], "host.timezone")),
        TlsConfig("cloudflare", email, token),
    )


def detect_repository(config: BootstrapConfig, runner: Runner, root: Path = ROOT) -> RepositoryConfig:
    """Return remote metadata for a clean checkout at its selected branch tip."""
    if runner.run(["git", "status", "--porcelain", "--untracked-files=no"], capture=True, cwd=root):
        raise BootstrapError("Repository has uncommitted tracked changes; commit them before bootstrap")
    branch = runner.run(["git", "branch", "--show-current"], capture=True, cwd=root)
    if not branch:
        raise BootstrapError("Repository is on a detached HEAD")
    url = runner.run(["git", "remote", "get-url", "origin"], capture=True, cwd=root)
    if config.repository_input:
        url, branch = config.repository_input["url"], config.repository_input["branch"]
    validate_repository_url(url)
    commit = runner.run(["git", "rev-parse", "HEAD"], capture=True, cwd=root)
    remote_line = runner.run(["git", "ls-remote", "--heads", url, f"refs/heads/{branch}"], capture=True, cwd=root)
    if (remote_line.split(maxsplit=1)[0] if remote_line else "") != commit:
        raise BootstrapError("The current commit is not the selected remote branch tip; push or select a reproducible revision")
    return RepositoryConfig(url, branch, commit)
