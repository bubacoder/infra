"""Shared types and safe command helpers for bootstrap."""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config/bootstrap.yaml"
SUPPORTED_SERVICES = ("security/traefik", "dashboard/homepage")
SERVICE_CONTAINERS = ("traefik", "logrotate", "homepage", "dockerproxy")


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


def remote(runner: Runner, target: str, command: str, *, capture: bool = False, timeout: int | None = None) -> str:
    return runner.run(["ssh", "-o", "BatchMode=yes", target, f"LC_ALL=C LANG=C {command}"], capture=capture, timeout=timeout)


def task(runner: Runner, name: str, timeout: int = 1200) -> None:
    runner.run(["task", name], timeout=timeout)


def private_key_for(public_key: Path) -> Path | None:
    private_key = public_key.with_suffix("")
    return private_key if private_key.is_file() else None


def vm_ssh_command(plan: BootstrapPlan, remote_command: str) -> list[str]:
    command = ["ssh", "-o", "BatchMode=yes"]
    if private_key := private_key_for(plan.config.vm.ssh_public_key):
        command.extend(["-i", str(private_key)])
    command.extend([f"{plan.config.vm.username}@{plan.config.network.expected_ipv4}", remote_command])
    return command
