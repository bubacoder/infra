#!/usr/bin/env python3
"""Plan and apply the supported first-time homelab deployment."""

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except ModuleNotFoundError:
    print("Error: 'yaml' module not found. Install it with: pip3 install pyyaml", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config/bootstrap.yaml"
SUPPORTED_SERVICES = ("security/traefik", "dashboard/homepage")
SERVICE_CONTAINERS = ("traefik", "logrotate", "homepage", "dockerproxy")
NAME_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
MAC_PATTERN = re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")
SHELL_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_.:/@+-]+")


class ConfigError(ValueError):
    """Bootstrap configuration is invalid."""


class BootstrapError(RuntimeError):
    """A bootstrap phase failed safely."""


@dataclass(frozen=True)
class RepositoryConfig:
    url: str
    branch: str
    commit: str


@dataclass(frozen=True)
class DeploymentConfig:
    admin_model: str
    services: tuple[str, ...]


@dataclass(frozen=True)
class ProxmoxConfig:
    ssh_target: str


@dataclass(frozen=True)
class VmConfig:
    vm_id: int | str
    name: str
    ubuntu_version: str
    username: str
    cpu_cores: int
    memory_max_mib: int
    memory_min_mib: int
    disk_size: str
    storage: str
    bridge: str
    mac: str | None
    ssh_public_key: Path


@dataclass(frozen=True)
class DnsConfig:
    mode: str
    verify: bool


@dataclass(frozen=True)
class NetworkConfig:
    expected_ipv4: str | None
    domain: str
    dns: DnsConfig


@dataclass(frozen=True)
class HostConfig:
    docker_volumes: str
    timezone: str


@dataclass(frozen=True)
class TlsConfig:
    provider: str
    acme_email: str
    token: str


@dataclass(frozen=True)
class BootstrapConfig:
    source: Path
    repository_input: dict[str, str] | None
    deployment: DeploymentConfig
    proxmox: ProxmoxConfig
    vm: VmConfig
    network: NetworkConfig
    host: HostConfig
    tls: TlsConfig


@dataclass(frozen=True)
class BootstrapPlan:
    config: BootstrapConfig
    repository: RepositoryConfig
    vm_id: int
    mac: str
    vm_exists: bool


class Runner:
    """Execute commands without shell interpolation or secret-bearing arguments."""

    def run(
        self,
        command: list[str],
        *,
        capture: bool = False,
        cwd: Path = ROOT,
        timeout: int | None = None,
    ) -> str:
        executable = command[0]
        if "/" not in executable:
            resolved = shutil.which(executable)
            if resolved is None:
                raise BootstrapError(f"Required executable is not installed: {executable}")
            command = [resolved, *command[1:]]
        try:
            result = subprocess.run(  # noqa: S603
                command,
                cwd=cwd,
                check=True,
                text=True,
                stdout=subprocess.PIPE if capture else None,
                stderr=subprocess.PIPE if capture else None,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise BootstrapError(f"Command timed out: {command[0]}") from error
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "").strip()
            suffix = f": {detail}" if detail else ""
            raise BootstrapError(f"Command failed: {command[0]}{suffix}") from error
        return result.stdout.strip() if capture else ""


def require_mapping(value: object, field: str, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{field} must be a mapping")
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        raise ConfigError(f"{field} contains unknown fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ConfigError(f"{field} is missing fields: {', '.join(sorted(missing))}")
    return value


def require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        raise ConfigError(f"{field} must be a non-empty string")
    return value.strip()


def require_positive_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ConfigError(f"{field} must be a positive integer")
    return value


def require_shell_token(value: object, field: str) -> str:
    token = require_string(value, field)
    if not SHELL_TOKEN_PATTERN.fullmatch(token):
        raise ConfigError(f"{field} contains unsupported characters")
    return token


def validate_file_security(path: Path, root: Path) -> Path:
    resolved = path.expanduser().resolve()
    config_dir = (root / "config").resolve()
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
    name = require_string(value, field).lower()
    if not NAME_PATTERN.fullmatch(name):
        raise ConfigError(f"{field} must be a valid lowercase hostname label")
    return name


def validate_mac(value: object, field: str = "vm.mac") -> str:
    mac = require_string(value, field).upper()
    if not MAC_PATTERN.fullmatch(mac):
        raise ConfigError(f"{field} must be a colon-separated MAC address")
    first_octet = int(mac[:2], 16)
    if first_octet & 1:
        raise ConfigError(f"{field} must be a unicast MAC address")
    return mac


def validate_domain(value: object) -> str:
    domain = require_string(value, "network.domain").lower().rstrip(".")
    labels = domain.split(".")
    if len(labels) < 2 or any(not NAME_PATTERN.fullmatch(label) for label in labels):
        raise ConfigError("network.domain must be a valid domain name")
    return domain


def validate_repository_url(url: str) -> None:
    if url.startswith("-"):
        raise ConfigError("repository.url is invalid")
    parsed = urlparse(url)
    if parsed.password or parsed.query or parsed.fragment:
        raise ConfigError("repository.url must not contain credentials")
    if parsed.scheme in {"http", "https"} and parsed.username:
        raise ConfigError("repository.url must not contain credentials")


def validate_repository_input(value: object) -> dict[str, str] | None:
    if value is None:
        return None
    repository = require_mapping(value, "repository", {"url", "branch"}, {"url", "branch"})
    url = require_string(repository["url"], "repository.url")
    validate_repository_url(url)
    branch = require_string(repository["branch"], "repository.branch")
    if branch.startswith("-") or any(character.isspace() for character in branch):
        raise ConfigError("repository.branch is invalid")
    return {"url": url, "branch": branch}


def load_config(path: Path, root: Path = ROOT) -> BootstrapConfig:  # noqa: PLR0912
    source = validate_file_security(path, root)
    try:
        raw = yaml.safe_load(source.read_text())
    except yaml.YAMLError as error:
        location = ""
        if error.problem_mark:
            location = f" at line {error.problem_mark.line + 1}, column {error.problem_mark.column + 1}"
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

    deployment_raw = require_mapping(
        document["deployment"],
        "deployment",
        {"admin_model", "services"},
        {"admin_model", "services"},
    )
    admin_model = require_string(deployment_raw["admin_model"], "deployment.admin_model")
    if admin_model != "separate":
        raise ConfigError("deployment.admin_model currently supports only 'separate'")
    services_raw = deployment_raw["services"]
    if not isinstance(services_raw, list) or any(not isinstance(service, str) for service in services_raw):
        raise ConfigError("deployment.services must be a list of service paths")
    services = tuple(services_raw)
    if services != SUPPORTED_SERVICES:
        raise ConfigError(f"deployment.services currently must be: {', '.join(SUPPORTED_SERVICES)}")

    proxmox_raw = require_mapping(document["proxmox"], "proxmox", {"ssh_target"}, {"ssh_target"})
    ssh_target = require_shell_token(proxmox_raw["ssh_target"], "proxmox.ssh_target")
    if ssh_target.startswith("-") or any(character.isspace() for character in ssh_target):
        raise ConfigError("proxmox.ssh_target is invalid")

    vm_raw = require_mapping(
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
    vm_id = vm_raw["id"]
    if vm_id != "auto" and (not isinstance(vm_id, int) or isinstance(vm_id, bool) or vm_id <= 0):
        raise ConfigError("vm.id must be a positive integer or 'auto'")
    memory_min = require_positive_int(vm_raw["memory_min_mib"], "vm.memory_min_mib")
    memory_max = require_positive_int(vm_raw["memory_max_mib"], "vm.memory_max_mib")
    if memory_min > memory_max:
        raise ConfigError("vm.memory_min_mib must not exceed vm.memory_max_mib")
    public_key = Path(require_string(vm_raw["ssh_public_key"], "vm.ssh_public_key")).expanduser().resolve()
    try:
        public_key_content = public_key.read_text().strip()
    except OSError as error:
        raise ConfigError(f"Cannot read vm.ssh_public_key: {error.strerror or 'I/O error'}") from error
    if not public_key.is_file() or not public_key_content.startswith(("ssh-ed25519 ", "ssh-rsa ", "ecdsa-")):
        raise ConfigError(f"vm.ssh_public_key is not a usable public key: {public_key}")
    mac = validate_mac(vm_raw["mac"]) if vm_raw.get("mac") else None

    network_raw = require_mapping(
        document["network"],
        "network",
        {"expected_ipv4", "domain", "dns"},
        {"expected_ipv4", "domain", "dns"},
    )
    expected_ipv4_value = require_string(network_raw["expected_ipv4"], "network.expected_ipv4")
    if expected_ipv4_value == "auto":
        expected_ipv4 = None
    else:
        try:
            expected_ipv4 = str(ipaddress.IPv4Address(expected_ipv4_value))
        except ipaddress.AddressValueError as error:
            raise ConfigError("network.expected_ipv4 must be an IPv4 address or 'auto'") from error
    dns_raw = require_mapping(network_raw["dns"], "network.dns", {"mode", "verify"}, {"mode", "verify"})
    if dns_raw["mode"] != "external" or dns_raw["verify"] is not True:
        raise ConfigError("network.dns currently requires mode: external and verify: true")

    host_raw = require_mapping(
        document["host"],
        "host",
        {"docker_volumes", "timezone"},
        {"docker_volumes", "timezone"},
    )
    docker_volumes = require_shell_token(host_raw["docker_volumes"], "host.docker_volumes")
    if not Path(docker_volumes).is_absolute():
        raise ConfigError("host.docker_volumes must be an absolute path")

    tls_raw = require_mapping(
        document["tls"],
        "tls",
        {"provider", "acme_email", "token"},
        {"provider", "acme_email", "token"},
    )
    if tls_raw["provider"] != "cloudflare":
        raise ConfigError("tls.provider currently supports only 'cloudflare'")
    email = require_string(tls_raw["acme_email"], "tls.acme_email")
    if "@" not in email:
        raise ConfigError("tls.acme_email must be an email address")
    token = require_string(tls_raw["token"], "tls.token")
    if token.startswith(("<", "replace-")):
        raise ConfigError("tls.token still contains a placeholder")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        raise ConfigError("tls.token contains unsupported characters")

    return BootstrapConfig(
        source=source,
        repository_input=validate_repository_input(document.get("repository")),
        deployment=DeploymentConfig(admin_model=admin_model, services=services),
        proxmox=ProxmoxConfig(ssh_target=ssh_target),
        vm=VmConfig(
            vm_id=vm_id,
            name=validate_name(vm_raw["name"], "vm.name"),
            ubuntu_version=require_shell_token(vm_raw["ubuntu_version"], "vm.ubuntu_version"),
            username=validate_name(vm_raw["username"], "vm.username"),
            cpu_cores=require_positive_int(vm_raw["cpu_cores"], "vm.cpu_cores"),
            memory_max_mib=memory_max,
            memory_min_mib=memory_min,
            disk_size=require_shell_token(vm_raw["disk_size"], "vm.disk_size"),
            storage=require_shell_token(vm_raw["storage"], "vm.storage"),
            bridge=require_shell_token(vm_raw["bridge"], "vm.bridge"),
            mac=mac,
            ssh_public_key=public_key,
        ),
        network=NetworkConfig(
            expected_ipv4=expected_ipv4,
            domain=validate_domain(network_raw["domain"]),
            dns=DnsConfig(mode="external", verify=True),
        ),
        host=HostConfig(
            docker_volumes=docker_volumes,
            timezone=require_shell_token(host_raw["timezone"], "host.timezone"),
        ),
        tls=TlsConfig(provider="cloudflare", acme_email=email, token=token),
    )


def remote(runner: Runner, target: str, command: str, *, capture: bool = False, timeout: int | None = None) -> str:
    return runner.run(["ssh", "-o", "BatchMode=yes", target, command], capture=capture, timeout=timeout)


def detect_repository(config: BootstrapConfig, runner: Runner, root: Path = ROOT) -> RepositoryConfig:
    dirty = runner.run(["git", "status", "--porcelain", "--untracked-files=no"], capture=True, cwd=root)
    if dirty:
        raise BootstrapError("Repository has uncommitted tracked changes; commit them before bootstrap")
    branch = runner.run(["git", "branch", "--show-current"], capture=True, cwd=root)
    if not branch:
        raise BootstrapError("Repository is on a detached HEAD")
    url = runner.run(["git", "remote", "get-url", "origin"], capture=True, cwd=root)
    if config.repository_input:
        url = config.repository_input["url"]
        branch = config.repository_input["branch"]
    validate_repository_url(url)
    commit = runner.run(["git", "rev-parse", "HEAD"], capture=True, cwd=root)
    remote_line = runner.run(["git", "ls-remote", "--heads", url, f"refs/heads/{branch}"], capture=True, cwd=root)
    remote_commit = remote_line.split(maxsplit=1)[0] if remote_line else ""
    if remote_commit != commit:
        raise BootstrapError("The current commit is not the selected remote branch tip; push or select a reproducible revision")
    return RepositoryConfig(url=url, branch=branch, commit=commit)


def generated_mac(target: str, vm_name: str) -> str:
    digest = hashlib.sha256(f"{target}\0{vm_name}".encode()).digest()
    octets = [0x02, digest[0], digest[1], digest[2], digest[3], digest[4]]
    return ":".join(f"{octet:02X}" for octet in octets)


def proxmox_vm_rows(config: BootstrapConfig, runner: Runner) -> list[tuple[int, str]]:
    output = remote(runner, config.proxmox.ssh_target, "sudo qm list", capture=True)
    rows: list[tuple[int, str]] = []
    for line in output.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2 and fields[0].isdigit():
            rows.append((int(fields[0]), fields[1]))
    return rows


def resolve_plan(config: BootstrapConfig, runner: Runner, root: Path = ROOT) -> BootstrapPlan:
    repository = detect_repository(config, runner, root)
    rows = proxmox_vm_rows(config, runner)
    named = next((vm_id for vm_id, name in rows if name == config.vm.name), None)
    if config.vm.vm_id == "auto":
        vm_id = named
        if vm_id is None:
            next_id = remote(runner, config.proxmox.ssh_target, "sudo pvesh get /cluster/nextid", capture=True)
            try:
                vm_id = int(next_id)
            except ValueError as error:
                raise BootstrapError("Proxmox returned an invalid next VM ID") from error
    else:
        vm_id = int(config.vm.vm_id)
        if named is not None and named != vm_id:
            raise BootstrapError(f"VM name {config.vm.name} already belongs to VM ID {named}")
    vm_exists = any(existing_id == vm_id for existing_id, _ in rows)
    if vm_exists and named != vm_id:
        raise BootstrapError(f"VM ID {vm_id} already exists with another name")
    return BootstrapPlan(
        config=config,
        repository=repository,
        vm_id=vm_id,
        mac=config.vm.mac or generated_mac(config.proxmox.ssh_target, config.vm.name),
        vm_exists=vm_exists,
    )


def print_plan(plan: BootstrapPlan) -> None:
    summary = {
        "repository": asdict(plan.repository),
        "deployment": asdict(plan.config.deployment),
        "proxmox": asdict(plan.config.proxmox),
        "vm": {
            **asdict(plan.config.vm),
            "id": plan.vm_id,
            "mac": plan.mac,
            "ssh_public_key": str(plan.config.vm.ssh_public_key),
            "exists": plan.vm_exists,
        },
        "network": {
            **asdict(plan.config.network),
            "expected_ipv4": plan.config.network.expected_ipv4 or "auto",
        },
        "host": asdict(plan.config.host),
        "tls": {
            "provider": plan.config.tls.provider,
            "acme_email": plan.config.tls.acme_email,
            "token": "<redacted>",
        },
    }
    print(yaml.safe_dump(summary, sort_keys=False).rstrip())


def verify_dns(plan: BootstrapPlan, expected: str, *, discovered: bool = False) -> None:
    names = [
        plan.config.network.domain,
        f"traefik.{plan.config.network.domain}",
        f"home.{plan.config.network.domain}",
    ]
    names.append(f"bootstrap-check.{plan.config.network.domain}")
    failures: list[str] = []
    for name in names:
        try:
            addresses = {entry[4][0] for entry in socket.getaddrinfo(name, None, socket.AF_INET)}
        except socket.gaierror:
            addresses = set()
        if addresses != {expected}:
            failures.append(name)
    if failures:
        if discovered:
            names_text = ", ".join(names)
            raise BootstrapError(
                f"Networking checkpoint: VM {plan.vm_id} was discovered at {expected}. "
                "Ask the operator to map its base domain and service names to that address, "
                f"then rerun bootstrap. Required names: {names_text}"
            )
        raise BootstrapError(
            "External DHCP/DNS checkpoint is incomplete. Reserve "
            f"{plan.mac} as {expected}, then point the base domain and wildcard to that address. Failed names: {', '.join(failures)}"
        )


def discover_vm_ipv4(plan: BootstrapPlan, runner: Runner) -> str:
    output = remote(
        runner,
        plan.config.proxmox.ssh_target,
        f"sudo qm guest cmd {plan.vm_id} network-get-interfaces",
        capture=True,
    )
    try:
        interfaces = json.loads(output)
        if isinstance(interfaces, dict):
            interfaces = interfaces.get("result", interfaces)
    except json.JSONDecodeError as error:
        raise BootstrapError(f"Could not read network interfaces from Proxmox guest agent for VM {plan.vm_id}") from error
    if not isinstance(interfaces, list):
        raise BootstrapError(f"Could not read network interfaces from Proxmox guest agent for VM {plan.vm_id}")

    addresses: set[str] = set()
    for interface in interfaces:
        if not isinstance(interface, dict) or str(interface.get("hardware-address", "")).upper() != plan.mac:
            continue
        for address in interface.get("ip-addresses", []):
            if not isinstance(address, dict) or address.get("ip-address-type") != "ipv4":
                continue
            try:
                ipv4 = ipaddress.IPv4Address(str(address.get("ip-address", "")))
            except ipaddress.AddressValueError:
                continue
            if not ipv4.is_loopback and not ipv4.is_unspecified and not ipv4.is_multicast:
                addresses.add(str(ipv4))
    if len(addresses) != 1:
        found = ", ".join(sorted(addresses)) or "none"
        raise BootstrapError(f"Expected exactly one usable IPv4 address on VM {plan.vm_id} interface {plan.mac}; found: {found}")
    return addresses.pop()


def with_expected_ipv4(plan: BootstrapPlan, expected_ipv4: str) -> BootstrapPlan:
    return replace(plan, config=replace(plan.config, network=replace(plan.config.network, expected_ipv4=expected_ipv4)))


def verify_existing_vm(plan: BootstrapPlan, runner: Runner) -> None:
    if not plan.vm_exists:
        return
    output = remote(runner, plan.config.proxmox.ssh_target, f"sudo qm config {plan.vm_id}", capture=True)
    normalized = output.upper()
    expected_fragments = (
        f"NAME: {plan.config.vm.name}".upper(),
        plan.mac,
        "SCSI0:",
        "IDE2:",
        "AGENT:",
        f"USER=LOCAL:SNIPPETS/UBUNTU-{plan.config.vm.ubuntu_version}-{plan.vm_id}-CLOUD-USER.YAML",
        f"NETWORK=LOCAL:SNIPPETS/UBUNTU-{plan.config.vm.ubuntu_version}-{plan.vm_id}-CLOUD-NETWORK.YAML",
    )
    if any(fragment not in normalized for fragment in expected_fragments):
        raise BootstrapError(
            f"Existing VM {plan.vm_id} is incomplete or does not match the expected name, MAC, disks, agent, and cloud-init configuration; "
            "inspect it before retrying"
        )


def preflight(plan: BootstrapPlan, runner: Runner) -> None:
    for tool in ("git", "task", "ssh", "ssh-keyscan", "rsync", "ansible-playbook", "curl"):
        if shutil.which(tool) is None:
            raise BootstrapError(f"Required executable is not installed: {tool}")
    verify_existing_vm(plan, runner)
    target = plan.config.proxmox.ssh_target
    storage = shlex.quote(plan.config.vm.storage)
    bridge = shlex.quote(plan.config.vm.bridge)
    remote(runner, target, f"sudo pvesm status --storage {storage} >/dev/null")
    remote(runner, target, f"ip link show {bridge} >/dev/null")
    storage_config = remote(
        runner,
        target,
        "sudo pvesh get /storage/local --output-format json",
        capture=True,
    )
    try:
        storage_content = json.loads(storage_config)["content"].split(",")
    except (json.JSONDecodeError, KeyError, AttributeError) as error:
        raise BootstrapError("Could not read Proxmox storage 'local' configuration") from error
    if "snippets" not in storage_content:
        raise BootstrapError("Proxmox storage 'local' must allow snippet content")
    if not plan.vm_exists:
        mac = shlex.quote(plan.mac)
        mac_status = remote(
            runner,
            target,
            f"sudo grep -Riq -- {mac} /etc/pve/qemu-server; code=$?; "
            "if [ $code -eq 0 ]; then printf used; elif [ $code -eq 1 ]; then printf available; else exit $code; fi",
            capture=True,
        )
        if mac_status != "available":
            raise BootstrapError(f"MAC address is already used: {plan.mac}")
    if plan.config.network.expected_ipv4:
        verify_dns(plan, plan.config.network.expected_ipv4)


def atomic_write(path: Path, content: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(temporary, flags, mode)
        with os.fdopen(descriptor, "w") as file:
            file.write(content)
        os.replace(temporary, path)
        path.chmod(mode)
    finally:
        temporary.unlink(missing_ok=True)


def render_services(services: tuple[str, ...]) -> str:
    categories: dict[str, list[dict[str, str]]] = {}
    for service in services:
        category, name = service.rsplit("/", 1)
        categories.setdefault(category, []).append({"name": name, "state": "up"})
    return yaml.safe_dump({"services": [{category: entries} for category, entries in categories.items()]}, sort_keys=False)


def render_vm_config(plan: BootstrapPlan, expected_ipv4: str, root: Path = ROOT) -> None:
    config = plan.config
    vm_dir = root / "config/vm/proxmox"
    public_key_target = vm_dir / "bootstrap-authorized-key.pub"
    atomic_write(public_key_target, config.vm.ssh_public_key.read_text(), 0o600)
    env = f"""# Generated by scripts/bootstrap.py. Do not edit manually.
PROXMOX_HOST={config.proxmox.ssh_target}
UBUNTU_VERSION={config.vm.ubuntu_version}
USERNAME={config.vm.username}
VMNAME={config.vm.name}
VMID={plan.vm_id}
CPU_CORES={config.vm.cpu_cores}
MAX_MEMORY_SIZE={config.vm.memory_max_mib}
MIN_MEMORY_SIZE={config.vm.memory_min_mib}
DISK_SIZE={config.vm.disk_size}
VM_STORAGE={config.vm.storage}
VM_BRIDGE={config.vm.bridge}
VM_MAC={plan.mac}
EXPECTED_IPV4={expected_ipv4}
SSH_PUBLIC_KEY_FILE=/tmp/vm/proxmox/bootstrap-authorized-key.pub
"""
    atomic_write(vm_dir / "ubuntu-cloud.env", env)


def render_config(plan: BootstrapPlan, root: Path = ROOT, expected_ipv4: str | None = None) -> None:
    config = plan.config
    expected_ipv4 = expected_ipv4 or config.network.expected_ipv4
    if expected_ipv4 is None:
        raise BootstrapError("Cannot render host configuration before the VM IPv4 address is known")
    render_vm_config(plan, expected_ipv4, root)

    inventory_path = root / "config/ansible/inventory/inventory.yaml"
    if inventory_path.exists():
        inventory = yaml.safe_load(inventory_path.read_text()) or {}
    else:
        inventory = yaml.safe_load((root / "config-example/ansible/inventory/inventory.yaml").read_text())
    debian_hosts = inventory.setdefault("debian", {}).setdefault("hosts", {})
    existing = debian_hosts.get(config.vm.name)
    desired_host: dict[str, object] = {
        "ansible_host": expected_ipv4,
        "ansible_user": config.vm.username,
        "debian_base_ssh_key_file": str(config.vm.ssh_public_key),
        "debian_docker_host_volumes_path": config.host.docker_volumes,
    }
    private_key = private_key_for(config.vm.ssh_public_key)
    if private_key:
        desired_host["ansible_ssh_private_key_file"] = str(private_key)
    if existing is not None and not isinstance(existing, dict):
        raise BootstrapError(f"Inventory host has an invalid value: {config.vm.name}")
    for key, value in desired_host.items():
        if existing and key in existing and existing[key] != value:
            raise BootstrapError(f"Inventory host has a conflicting {key}: {config.vm.name}")
    debian_hosts[config.vm.name] = {**(existing or {}), **desired_host}
    docker_hosts = inventory.setdefault("docker_hosts", {}).setdefault("hosts", {})
    if not isinstance(docker_hosts, dict):
        raise BootstrapError("docker_hosts.hosts must be a mapping")
    docker_hosts.setdefault(config.vm.name, None)
    atomic_write(inventory_path, yaml.safe_dump(inventory, sort_keys=False))

    docker_dir = root / f"config/docker/{config.vm.name}"
    host_env = f"""# Generated by scripts/bootstrap.py. Do not edit manually.
TIMEZONE={config.host.timezone}
MYDOMAIN={config.network.domain}
ADMIN_EMAIL={config.tls.acme_email}
DOCKER_VOLUMES={config.host.docker_volumes}
STORAGE_BACKGROUNDS=${{DOCKER_VOLUMES}}/homepage/backgrounds
CROWDSEC_ENABLED=false
"""
    atomic_write(docker_dir / ".env", host_env)
    atomic_write(
        docker_dir / ".env.traefik",
        f"CLOUDFLARE_DNS_API_TOKEN={config.tls.token}\nCROWDSEC_BOUNCER_API_KEY=\n",
    )
    atomic_write(docker_dir / "services.yaml", render_services(config.deployment.services))


def task(runner: Runner, name: str, timeout: int = 1200) -> None:
    runner.run(["task", name], timeout=timeout)


def provision_vm(plan: BootstrapPlan, runner: Runner) -> None:
    if plan.vm_exists:
        status = remote(runner, plan.config.proxmox.ssh_target, f"sudo qm status {plan.vm_id}", capture=True)
        if "status: running" not in status:
            remote(runner, plan.config.proxmox.ssh_target, f"sudo qm start {plan.vm_id}")
        task(runner, "bootstrap:vm-wait")
        return
    task(runner, "bootstrap:vm-preflight")
    task(runner, "bootstrap:vm-provision")


def private_key_for(public_key: Path) -> Path | None:
    private_key = public_key.with_suffix("")
    return private_key if private_key.is_file() else None


def vm_ssh_command(plan: BootstrapPlan, remote_command: str) -> list[str]:
    command = ["ssh", "-o", "BatchMode=yes"]
    if private_key := private_key_for(plan.config.vm.ssh_public_key):
        command.extend(["-i", str(private_key)])
    command.extend([f"{plan.config.vm.username}@{plan.config.network.expected_ipv4}", remote_command])
    return command


def establish_ssh_trust(plan: BootstrapPlan, runner: Runner) -> None:
    target = plan.config.proxmox.ssh_target
    guest_result = remote(runner, target, f"sudo qm guest exec {plan.vm_id} -- cat /etc/ssh/ssh_host_ed25519_key.pub", capture=True)
    try:
        guest_key = json.loads(guest_result)["out-data"].split()[1]
    except (KeyError, IndexError, json.JSONDecodeError) as error:
        raise BootstrapError("Could not read the VM SSH host key through the Proxmox guest agent") from error
    scan = runner.run(
        ["ssh-keyscan", "-T", "10", "-t", "ed25519", plan.config.network.expected_ipv4],
        capture=True,
    )
    network_key = None
    for line in scan.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[1] == "ssh-ed25519":
            network_key = fields[2]
            break
    if not network_key or network_key != guest_key:
        raise BootstrapError("The VM SSH host key does not match the key presented on the network")
    command = vm_ssh_command(plan, "true")
    command[1:1] = ["-o", "StrictHostKeyChecking=accept-new"]
    runner.run(command)


def configure_host(plan: BootstrapPlan, runner: Runner) -> None:
    runner.run(["ansible/apply-homelab.sh", "--limit", plan.config.vm.name], timeout=1800)
    expected_name = shlex.quote(plan.config.vm.name)
    runner.run(
        vm_ssh_command(
            plan,
            "docker info >/dev/null && docker compose version >/dev/null && task --version >/dev/null && "
            f'test "$(hostname --short)" = {expected_name} && test "$(hostname)" = {expected_name}',
        )
    )


def prepare_remote_repository(plan: BootstrapPlan, runner: Runner, root: Path = ROOT) -> None:
    repository = plan.repository
    checkout = "$HOME/repos/infra"
    branch = shlex.quote(repository.branch)
    url = shlex.quote(repository.url)
    clone = f"mkdir -p $HOME/repos; git clone --branch {branch} --single-branch {url} {checkout}"
    checkout_state = runner.run(
        vm_ssh_command(
            plan,
            f"if test -d {checkout}/.git; then printf repository; elif test -e {checkout}; then printf invalid; else printf missing; fi",
        ),
        capture=True,
        timeout=30,
    )
    if checkout_state == "invalid":
        raise BootstrapError(f"Remote checkout path exists but is not a Git repository: {checkout}")
    if checkout_state == "missing":
        runner.run(vm_ssh_command(plan, clone), timeout=300)
    elif checkout_state == "repository":
        update = (
            f'test -z "$(git -C {checkout} status --porcelain --untracked-files=no)" && '
            f'test "$(git -C {checkout} branch --show-current)" = {branch} && '
            f"git -C {checkout} fetch origin {branch} && "
            f"git -C {checkout} merge --ff-only {shlex.quote(repository.commit)}"
        )
        runner.run(vm_ssh_command(plan, update), timeout=300)
    else:
        raise BootstrapError("Could not determine the remote repository state")
    expected_commit = shlex.quote(repository.commit)
    runner.run(vm_ssh_command(plan, f'test "$(git -C {checkout} rev-parse HEAD)" = {expected_commit}'), timeout=30)

    services_path = f"{checkout}/config/docker/{plan.config.vm.name}/services.yaml"
    initialized = runner.run(vm_ssh_command(plan, f"test -f {services_path} && printf yes || true"), capture=True)
    if initialized != "yes":
        runner.run(vm_ssh_command(plan, f"cd {checkout} && task bootstrap:init-local-config"))
    target = f"{plan.config.vm.username}@{plan.config.network.expected_ipv4}:repos/infra/config/docker/{plan.config.vm.name}/"
    ssh_transport = "ssh -o BatchMode=yes"
    if private_key := private_key_for(plan.config.vm.ssh_public_key):
        ssh_transport += f" -i {shlex.quote(str(private_key))}"
    rsync = ["rsync", "-a", "-e", ssh_transport]
    rsync.extend([f"{root}/config/docker/{plan.config.vm.name}/", target])
    runner.run(rsync, timeout=120)
    runner.run(vm_ssh_command(plan, f"chmod 600 {checkout}/config/docker/{plan.config.vm.name}/.env.traefik"))
    runner.run(vm_ssh_command(plan, f"cd {checkout} && task docker:check-host"))


def deploy_services(plan: BootstrapPlan, runner: Runner) -> None:
    runner.run(vm_ssh_command(plan, "cd $HOME/repos/infra && task docker:apply"), timeout=1800)


def verify_services(plan: BootstrapPlan, runner: Runner, timeout: int = 180) -> None:
    checkout = "$HOME/repos/infra"
    containers = " ".join(SERVICE_CONTAINERS)
    status_command = f"docker inspect --format '{{{{.State.Running}}}}:{{{{.RestartCount}}}}' {containers}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            statuses = runner.run(
                vm_ssh_command(plan, status_command),
                capture=True,
                timeout=20,
            ).splitlines()
            if len(statuses) == len(SERVICE_CONTAINERS) and all(status.startswith("true:") for status in statuses):
                domain = plan.config.network.domain
                urls = [f"https://home.{domain}/", f"https://traefik.{domain}/dashboard/"]
                for url in urls:
                    runner.run(
                        [
                            "curl",
                            "--fail",
                            "--silent",
                            "--show-error",
                            "--connect-timeout",
                            "5",
                            "--max-time",
                            "15",
                            "--output",
                            "/dev/null",
                            url,
                        ],
                        timeout=20,
                    )
                break
        except BootstrapError:
            pass
        time.sleep(5)
    else:
        raise BootstrapError("Core services did not become stable and reachable before the timeout")

    stable_before = runner.run(vm_ssh_command(plan, status_command), capture=True, timeout=20)
    time.sleep(10)
    stable_after = runner.run(vm_ssh_command(plan, status_command), capture=True, timeout=20)
    if stable_before != stable_after:
        raise BootstrapError("Core containers did not remain stable during the acceptance interval")

    persistence = (
        f"test -s {shlex.quote(plan.config.host.docker_volumes)}/traefik/letsencrypt/acme.json && "
        f"test -d {shlex.quote(plan.config.host.docker_volumes)}/traefik/logs && "
        f"test -d {shlex.quote(plan.config.host.docker_volumes)}/homepage/logs"
    )
    runner.run(vm_ssh_command(plan, persistence))

    id_command = f"docker inspect --format '{{{{.Id}}}}' {containers}"
    before = runner.run(vm_ssh_command(plan, id_command), capture=True, timeout=20)
    runner.run(vm_ssh_command(plan, f"cd {checkout} && task docker:apply"), timeout=1800)
    after = runner.run(vm_ssh_command(plan, id_command), capture=True, timeout=20)
    if before != after:
        raise BootstrapError("Repeat deployment unexpectedly recreated core containers")


def confirm(plan: BootstrapPlan) -> None:
    prompt = f"Create or resume VM {plan.config.vm.name} (ID {plan.vm_id}) and deploy core services? [y/N] "
    response = input(prompt).strip().lower()
    if response not in {"y", "yes"}:
        raise BootstrapError("Bootstrap cancelled")


def apply(plan: BootstrapPlan, runner: Runner, *, assume_yes: bool = False, root: Path = ROOT) -> None:
    if not assume_yes:
        confirm(plan)
    print("[1/7] Rendering VM configuration")
    render_vm_config(plan, plan.config.network.expected_ipv4 or "", root)
    print("[2/7] Provisioning or resuming the VM")
    provision_vm(plan, runner)
    expected_ipv4 = plan.config.network.expected_ipv4
    if expected_ipv4 is None:
        expected_ipv4 = discover_vm_ipv4(plan, runner)
        print(f"Discovered VM {plan.vm_id} IPv4 address: {expected_ipv4}")
        verify_dns(plan, expected_ipv4, discovered=True)
        plan = with_expected_ipv4(plan, expected_ipv4)
    print("[3/7] Rendering host configuration")
    render_config(plan, root, expected_ipv4)
    print("[4/7] Verifying and trusting the VM SSH host key")
    establish_ssh_trust(plan, runner)
    print("[5/7] Configuring the Docker host with Ansible")
    configure_host(plan, runner)
    print("[6/7] Preparing the remote repository and service configuration")
    prepare_remote_repository(plan, runner, root)
    print("[7/7] Deploying services")
    deploy_services(plan, runner)
    print("Verifying service health, TLS, DNS, persistence, and repeat deployment")
    verify_services(plan, runner)
    print("Bootstrap completed successfully.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Bootstrap YAML path")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--plan", action="store_true", help="Validate and print a redacted plan")
    operation.add_argument("--apply", action="store_true", help="Apply or resume the deployment")
    parser.add_argument("--yes", action="store_true", help="Skip the apply confirmation prompt")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.yes and not args.apply:
        raise ConfigError("--yes requires --apply")
    runner = Runner()
    config = load_config(args.config)
    plan = resolve_plan(config, runner)
    print_plan(plan)
    preflight(plan, runner)
    print("Preflight passed.")
    if args.apply:
        apply(plan, runner, assume_yes=args.yes)


if __name__ == "__main__":
    try:
        main()
    except (BootstrapError, ConfigError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
