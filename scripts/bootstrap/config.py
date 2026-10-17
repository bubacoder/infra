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
    AdguardDnsConfig,
    AwsConfig,
    AwsVmConfig,
    BootstrapConfig,
    BootstrapError,
    CloudflareDnsConfig,
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
    keys = set(value)
    unknown, missing = keys - allowed, required - keys
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
    labels = domain.split(".")
    if len(labels) < 2 or any(not NAME_PATTERN.fullmatch(label) for label in labels):
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


def load_config(path: Path, root: Path = ROOT) -> BootstrapConfig:
    """Load and validate a bootstrap YAML document."""
    source = validate_file_security(path, root)
    try:
        raw = yaml.safe_load(source.read_text())
    except yaml.YAMLError as error:
        location = f" at line {error.problem_mark.line + 1}, column {error.problem_mark.column + 1}" if error.problem_mark else ""
        raise ConfigError(f"Cannot parse bootstrap configuration{location}") from error
    except OSError as error:
        raise ConfigError(f"Cannot read bootstrap configuration: {error.strerror or 'I/O error'}") from error
    return parse_document(raw, source)


def parse_document(raw: object, source: Path) -> BootstrapConfig:
    """Validate an in-memory document without writing secrets to intermediate files."""
    document = require_mapping(
        raw,
        "bootstrap configuration",
        {"version", "repository", "deployment", "target", "proxmox", "aws", "vm", "network", "host", "tls"},
        {"version", "deployment", "vm", "network", "host", "tls"},
    )
    version = document["version"]
    if type(version) is not int or version not in (1, 2):
        raise ConfigError("version must be 1 or 2")
    target = document.get("target", "proxmox")
    if version == 1 and ("target" in document or "aws" in document):
        raise ConfigError("version 1 supports Proxmox only; use version 2 for target selection")
    if version == 2 and "target" not in document:
        raise ConfigError("version 2 requires target: proxmox or aws")
    if target not in ("proxmox", "aws"):
        raise ConfigError("target must be proxmox or aws")
    if target == "aws":
        return load_aws_config(document, source)
    return load_proxmox_config(document, source)


def load_proxmox_config(document: dict[str, Any], source: Path) -> BootstrapConfig:
    """Validate Proxmox-specific fields after document version and target checks."""
    if "proxmox" not in document or "aws" in document:
        raise ConfigError("Proxmox requires proxmox configuration and forbids aws configuration")
    shared = load_shared_config(document)
    proxmox = require_mapping(document["proxmox"], "proxmox", {"ssh_target"}, {"ssh_target"})
    ssh_target = require_shell_token(proxmox["ssh_target"], "proxmox.ssh_target")
    if ssh_target.startswith("-"):
        raise ConfigError("proxmox.ssh_target is invalid")
    required_vm_fields = {
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
    }
    vm = require_mapping(document["vm"], "vm", required_vm_fields | {"mac"}, required_vm_fields)
    vm_id = vm["id"]
    if vm_id != "auto" and (not isinstance(vm_id, int) or isinstance(vm_id, bool) or vm_id <= 0):
        raise ConfigError("vm.id must be a positive integer or 'auto'")
    memory_min, memory_max = (
        require_positive_int(vm["memory_min_mib"], "vm.memory_min_mib"),
        require_positive_int(vm["memory_max_mib"], "vm.memory_max_mib"),
    )
    if memory_min > memory_max:
        raise ConfigError("vm.memory_min_mib must not exceed vm.memory_max_mib")
    public_key = load_public_key(vm)
    return BootstrapConfig(
        source=source,
        proxmox=ProxmoxConfig(ssh_target),
        vm=VmConfig(
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
        **shared,
    )


def load_public_key(vm: dict[str, Any]) -> Path:
    """Validate the shared administrator public-key field."""
    public_key = Path(require_string(vm["ssh_public_key"], "vm.ssh_public_key")).expanduser().resolve()
    try:
        public_key_content = public_key.read_text().strip()
    except OSError as error:
        raise ConfigError(f"Cannot read vm.ssh_public_key: {error.strerror or 'I/O error'}") from error
    if not public_key.is_file() or not public_key_content.startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-")):
        raise ConfigError(f"vm.ssh_public_key is not a usable public key: {public_key}")
    return public_key


def load_shared_config(document: dict[str, Any]) -> dict[str, Any]:
    """Validate the same deployment, network, host and secret rules for all targets."""
    deployment = require_mapping(document["deployment"], "deployment", {"admin_model", "services"}, {"admin_model", "services"})
    if require_string(deployment["admin_model"], "deployment.admin_model") != "separate":
        raise ConfigError("deployment.admin_model currently supports only 'separate'")
    if not isinstance(deployment["services"], list) or any(not isinstance(service, str) for service in deployment["services"]):
        raise ConfigError("deployment.services must be a list of service paths")
    services = tuple(deployment["services"])
    if services != SUPPORTED_SERVICES:
        raise ConfigError(f"deployment.services currently must be: {', '.join(SUPPORTED_SERVICES)}")
    network = require_mapping(document["network"], "network", {"expected_ipv4", "domain", "dns"}, {"expected_ipv4", "domain", "dns"})
    expected_value = require_string(network["expected_ipv4"], "network.expected_ipv4")
    try:
        expected_ipv4 = None if expected_value == "auto" else str(ipaddress.IPv4Address(expected_value))
    except ipaddress.AddressValueError as error:
        raise ConfigError("network.expected_ipv4 must be an IPv4 address or 'auto'") from error
    dns = load_dns_config(network["dns"], validate_domain(network["domain"]), document.get("target", "proxmox"))
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
    return {
        "repository_input": validate_repository_input(document.get("repository")),
        "deployment": DeploymentConfig("separate", services),
        "network": NetworkConfig(expected_ipv4, validate_domain(network["domain"]), dns),
        "host": HostConfig(docker_volumes, require_shell_token(host["timezone"], "host.timezone")),
        "tls": TlsConfig("cloudflare", email, token),
    }


def load_dns_config(value: object, domain: str, target: str = "proxmox") -> DnsConfig:
    """Default to enabled target-aware DNS; retain legacy mode aliases."""
    dns = require_mapping(value, "network.dns", {"enabled", "mode", "verify", "cloudflare", "adguard"}, set())
    mode = dns.get("mode", "managed")
    if mode not in ("managed", "external") or dns.get("verify", True) is not True:
        raise ConfigError("network.dns requires mode: managed or external and verify: true")
    enabled = dns.get("enabled", mode == "managed")
    if type(enabled) is not bool:
        raise ConfigError("network.dns.enabled must be true or false")
    if "enabled" in dns and "mode" in dns and enabled != (mode == "managed"):
        raise ConfigError("network.dns.enabled conflicts with legacy network.dns.mode; remove mode or make them agree")
    mode = "managed" if enabled else "external"
    cloudflare, adguard = None, None
    if "cloudflare" in dns:
        if target != "aws":
            raise ConfigError("Proxmox public DNS is handled by DDNS; omit network.dns.cloudflare")
        cf = require_mapping(dns["cloudflare"], "network.dns.cloudflare", {"zone"}, {"zone"})
        zone = validate_domain(cf["zone"])
        if domain != zone and not domain.endswith(f".{zone}"):
            raise ConfigError("network.domain must belong to network.dns.cloudflare.zone")
        cloudflare = CloudflareDnsConfig(zone)
    if "adguard" in dns:
        ag = require_mapping(dns["adguard"], "network.dns.adguard", {"url", "username", "password"}, {"url", "username", "password"})
        url = require_string(ag["url"], "network.dns.adguard.url").rstrip("/")
        try:
            parsed = urlparse(url)
            port = parsed.port
        except ValueError:
            raise ConfigError("network.dns.adguard.url is invalid") from None
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path
            or (port is not None and port <= 0)
            or (parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1"}))
        ):
            raise ConfigError("network.dns.adguard.url must be an HTTPS origin, or HTTP on a numeric loopback address; no embedded credentials")
        username = require_string(ag["username"], "network.dns.adguard.username")
        if ":" in username:
            raise ConfigError("network.dns.adguard.username must not contain a colon")
        password = ag["password"]
        if not isinstance(password, str) or not password or any(char in password for char in "\r\n"):
            raise ConfigError("network.dns.adguard.password must be a nonempty single-line string")
        adguard = AdguardDnsConfig(url, username, password)
    if mode == "managed" and target == "aws" and cloudflare is None:
        raise ConfigError("Managed AWS DNS requires network.dns.cloudflare.zone; AdGuard is optional")
    return DnsConfig(mode, True, cloudflare, adguard)


def load_aws_config(document: dict[str, Any], source: Path) -> BootstrapConfig:
    """Validate AWS-specific fields and reuse shared version 1 validation."""
    if "proxmox" in document or "aws" not in document:
        raise ConfigError("AWS requires aws configuration and forbids proxmox configuration")
    vm = require_mapping(document["vm"], "vm", {"name", "username", "ssh_public_key"}, {"name", "username", "ssh_public_key"})
    if vm["username"] != "ubuntu":
        raise ConfigError("AWS currently requires vm.username: ubuntu")
    fields = {
        "account_id",
        "region",
        "profile",
        "ubuntu_version",
        "architecture",
        "instance_type",
        "admin_source_cidr",
        "os_disk_size_gb",
        "data_disk_size_gb",
    }
    aws = require_mapping(document["aws"], "aws", fields, fields - {"profile"})
    account = require_string(aws["account_id"], "aws.account_id")
    if not re.fullmatch(r"[0-9]{12}", account):
        raise ConfigError("aws.account_id must be a quoted 12-digit account ID")
    if aws["architecture"] != "x86_64":
        raise ConfigError("AWS bootstrap currently supports x86_64 only")
    try:
        cidr = ipaddress.IPv4Network(require_string(aws["admin_source_cidr"], "aws.admin_source_cidr"), strict=True)
    except ValueError as error:
        raise ConfigError("aws.admin_source_cidr must be a valid IPv4 network CIDR") from error
    if cidr.prefixlen == 0 or not cidr.network_address.is_global or not cidr.broadcast_address.is_global:
        raise ConfigError("aws.admin_source_cidr must restrict access to public administrator addresses")
    region = require_string(aws["region"], "aws.region")
    if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-[0-9]+", region):
        raise ConfigError("aws.region is invalid")
    instance = require_string(aws["instance_type"], "aws.instance_type")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*", instance):
        raise ConfigError("aws.instance_type is invalid")
    profile = require_shell_token(aws["profile"], "aws.profile") if aws.get("profile") else None
    shared = load_shared_config(document)
    volumes = Path(shared["host"].docker_volumes)
    if not volumes.is_relative_to("/storage") or volumes == Path("/storage") or ".." in volumes.parts:
        raise ConfigError("AWS host.docker_volumes must be beneath /storage")
    return BootstrapConfig(
        source=source,
        proxmox=None,
        vm=AwsVmConfig(validate_name(vm["name"], "vm.name"), "ubuntu", load_public_key(vm)),
        target="aws",
        aws=AwsConfig(
            account,
            region,
            profile,
            require_shell_token(aws["ubuntu_version"], "aws.ubuntu_version"),
            "x86_64",
            instance,
            str(cidr),
            require_positive_int(aws["os_disk_size_gb"], "aws.os_disk_size_gb"),
            require_positive_int(aws["data_disk_size_gb"], "aws.data_disk_size_gb"),
        ),
        **shared,
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
