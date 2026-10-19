"""Compile private operator inputs; native tools retain lifecycle/state ownership.

Never log input values or parser exceptions: the entire source file is private.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
VM_KEYS = {"name", "username", "ssh_public_key", "ssh_private_key"}
HOST_KEYS = {"domain", "acme_email", "timezone", "docker_volumes", "repository_url", "repository_ref"}
DNS_KEYS = {"enabled", "cloudflare_zone", "adguard_url", "adguard_urls"}
SECRET_KEYS = {"cloudflare_token", "adguard_username", "adguard_password"}
SERVICE_KEYS = {"security/traefik", "dashboard/homepage"}
PVE_ENV = {
    "host": "PROXMOX_HOST",
    "vmid": "VMID",
    "ubuntu_version": "UBUNTU_VERSION",
    "cpu_cores": "CPU_CORES",
    "memory_max_mib": "MAX_MEMORY_SIZE",
    "memory_min_mib": "MIN_MEMORY_SIZE",
    "disk_size": "DISK_SIZE",
    "storage": "VM_STORAGE",
    "bridge": "VM_BRIDGE",
    "mac": "VM_MAC",
}
PVE_KEYS = set(PVE_ENV) | {"address"}
AWS_KEYS = {
    "expected_account_id",
    "aws_region",
    "admin_source_address",
    "architecture",
    "instance_type",
    "allocate_elastic_ip",
    "os_disk_size_gb",
    "data_disk_size_gb",
    "ami_id",
}
ACTIONS = ("plan", "apply", "configure", "verify", "destroy-plan", "destroy", "destroy-cleanup", "vm-preflight", "vm-provision", "vm-wait")


class ConfigError(Exception):
    """An operator-safe error containing field names, never private values."""


class UniqueLoader(yaml.SafeLoader):
    """Reject ambiguous mappings rather than silently keeping the last value."""


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise ConfigError("Configuration requires unique string mapping keys.")
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def regular(path: Path, *, private: bool = True) -> None:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or (private and stat.S_IMODE(info.st_mode) & 0o077):
        raise ConfigError("Inputs and artifacts must be regular files with private permissions (0600).")


def private_directory(path: Path) -> None:
    if path.is_symlink():
        raise ConfigError("Refusing a symlinked configuration/artifact directory.")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ConfigError("Configuration/artifact directories must have private permissions (0700).")


def write_private(path: Path, content: str) -> None:
    if path.exists() or path.is_symlink():
        regular(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".bootstrap-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_yaml(path: Path, *, private: bool = True) -> dict:
    regular(path, private=private)
    try:
        result = yaml.load(path.read_text(), Loader=UniqueLoader)  # noqa: S506 -- SafeLoader subclass only adds duplicate-key rejection
    except yaml.YAMLError:
        raise ConfigError("Invalid private YAML; correct it privately. Values are not displayed.") from None
    if not isinstance(result, dict):
        raise ConfigError("Configuration must be a mapping.")
    return result


def section(config: dict, name: str, allowed: set, required: set | None = None) -> dict:
    value = config.get(name)
    if not isinstance(value, dict) or set(value) - allowed or (required or set()) - set(value):
        raise ConfigError(f"Check required/unknown fields in {name}; see the tracked template.")
    return value


def validate(config: dict, target: str, root: Path = ROOT) -> None:
    if set(config) != {"version", "target", "vm", "host", "dns", "secrets", "roles", "services", target}:
        raise ConfigError("Check top-level fields against the selected target's template.")
    if type(config["version"]) is not int or config["version"] != 1 or config["target"] != target:
        raise ConfigError("Unsupported version or TARGET mismatch; select the original target/directory.")
    vm = section(config, "vm", VM_KEYS, VM_KEYS)
    validate_selection(config, root)
    dns = section(config, "dns", DNS_KEYS, {"enabled"})
    host_required = set(HOST_KEYS) if config["services"] else ({"docker_volumes"} if "debian_docker_host" in config["roles"] else set())
    if dns["enabled"]:
        host_required |= {"domain"}
    host = section(config, "host", HOST_KEYS, host_required)
    cloudflare_required = bool(config["services"]) or (target == "aws" and dns["enabled"])
    secret_required = {"cloudflare_token"} if cloudflare_required else set()
    if dns["enabled"] and (dns.get("adguard_url") or dns.get("adguard_urls")):
        secret_required |= {"adguard_username", "adguard_password"}
    secrets = section(config, "secrets", SECRET_KEYS, secret_required)
    for group, fields in ((vm, VM_KEYS), (host, set(host)), (secrets, set(secrets))):
        if any(not isinstance(group[key], str) or not group[key] or "\x00" in group[key] for key in fields):
            raise ConfigError("VM, host and secret fields must be nonempty strings.")
    if not vm["ssh_public_key"].endswith(".pub"):
        raise ConfigError("vm.ssh_public_key must reference a .pub file; private keys are never read.")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", vm["name"]):
        raise ConfigError("vm.name must be a valid lowercase host name.")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]*", vm["username"]):
        raise ConfigError("vm.username must be a valid Linux user name.")
    if type(dns["enabled"]) is not bool:
        raise ConfigError("dns.enabled must be a boolean.")
    if "adguard_url" in dns and "adguard_urls" in dns:
        raise ConfigError("Use dns.adguard_url or dns.adguard_urls, not both.")
    endpoints = dns.get("adguard_urls", [dns["adguard_url"]] if "adguard_url" in dns else [])
    if not isinstance(endpoints, list) or any(not isinstance(url, str) for url in endpoints) or len(set(endpoints)) != len(endpoints):
        raise ConfigError("AdGuard endpoints must be a list of unique HTTP(S) origins.")
    for url in endpoints:
        try:
            parsed = urlsplit(url)
            valid = parsed.scheme in ("http", "https") and parsed.hostname and parsed.port != 0
            valid = valid and not (
                parsed.username is not None or parsed.password is not None or parsed.path or "?" in url or "#" in url or re.search(r"\s", url)
            )
        except ValueError:
            valid = False
        if not valid:
            raise ConfigError("AdGuard endpoints must be HTTP(S) origins without credentials, paths, queries or fragments.")
    validate_platform(config, target)


def validate_selection(config: dict, root: Path) -> None:
    for field in ("roles", "services"):
        value = config[field]
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value) or len(set(value)) != len(value):
            raise ConfigError(f"{field} must be an ordered list of unique names.")
    roles_root = (root / "ansible/roles").resolve()
    for role in config["roles"]:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", role):
            raise ConfigError("Roles must be local repository role names, not paths or collection names.")
        directory = roles_root / role
        if not directory.resolve().is_relative_to(roles_root) or not any(
            (directory / f"tasks/main.{suffix}").is_file() for suffix in ("yaml", "yml")
        ):
            raise ConfigError("A selected role is not available under ansible/roles. Add it before selecting it.")
    services = config["services"]
    if set(services) - SERVICE_KEYS:
        raise ConfigError("Unsupported bootstrap service; currently supported: security/traefik, dashboard/homepage.")
    if services and "debian_docker_host" not in config["roles"]:
        raise ConfigError("Docker services require the debian_docker_host role.")
    if services and "k3s" in config["roles"]:
        raise ConfigError("The default k3s role requires services: []; bundled Traefik uses ports 80/443.")
    if "dashboard/homepage" in services and "security/traefik" not in services:
        raise ConfigError("The bootstrap Homepage profile requires security/traefik.")


def validate_platform(config: dict, target: str) -> None:
    vm, dns = config["vm"], config["dns"]
    if target == "proxmox":
        pve = section(config, target, PVE_KEYS, PVE_KEYS)
        for key in ("vmid", "cpu_cores", "memory_max_mib", "memory_min_mib"):
            if type(pve[key]) is not int or pve[key] <= 0:
                raise ConfigError(f"proxmox.{key} must be a positive integer.")
        if pve["memory_min_mib"] > pve["memory_max_mib"]:
            raise ConfigError("Proxmox minimum memory must not exceed maximum memory.")
        for key in PVE_KEYS - {"vmid", "cpu_cores", "memory_max_mib", "memory_min_mib"}:
            if not isinstance(pve[key], str) or not re.fullmatch(r"[A-Za-z0-9_.:@/-]*", pve[key]) or (not pve[key] and key != "mac"):
                raise ConfigError(f"proxmox.{key} must be a plain safe token (only mac may be empty).")
        if not pve["host"] or pve["host"].startswith("-") or ":" in pve["host"]:
            raise ConfigError("proxmox.host must be a trusted SSH alias or user@host.")
        if not re.fullmatch(r"[1-9][0-9]*[GM]", pve["disk_size"]):
            raise ConfigError("proxmox.disk_size must be a positive size in G or M.")
        if pve["address"] != "auto":
            try:
                ipaddress.IPv4Address(pve["address"])
            except ValueError:
                raise ConfigError("proxmox.address must be auto or an IPv4 address.") from None
        if dns.get("cloudflare_zone"):
            raise ConfigError("Proxmox public address DNS remains externally managed; omit dns.cloudflare_zone.")
    else:
        aws = section(config, target, AWS_KEYS, AWS_KEYS - {"ami_id"})
        if vm["username"] != "ubuntu":
            raise ConfigError("AWS bootstrap requires vm.username: ubuntu.")
        for key in AWS_KEYS - {"ami_id", "allocate_elastic_ip", "os_disk_size_gb", "data_disk_size_gb"}:
            if not isinstance(aws[key], str):
                raise ConfigError(f"aws.{key} must be a string.")
        if type(aws["allocate_elastic_ip"]) is not bool:
            raise ConfigError("aws.allocate_elastic_ip must be a boolean.")
        for key in ("os_disk_size_gb", "data_disk_size_gb"):
            if type(aws[key]) is not int or aws[key] <= 0:
                raise ConfigError(f"aws.{key} must be a positive integer.")


def executable(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise ConfigError(f"Required controller executable is missing: {name}.")
    return path


def public_key(path: str) -> str:
    key = Path(path).expanduser()
    if not path.endswith(".pub"):
        raise ConfigError("Select an existing .pub file; private keys are never read.")
    regular(key, private=False)
    result = subprocess.run([executable("ssh-keygen"), "-l", "-f", str(key)], capture_output=True, timeout=15, check=False)  # noqa: S603
    if result.returncode:
        raise ConfigError("The selected public key failed OpenSSH validation.")
    value = " ".join(key.read_text().split()[:2])
    if not re.fullmatch(r"(?:ssh-ed25519|ssh-rsa|ecdsa-sha2-\S+) [A-Za-z0-9+/=]+", value):
        raise ConfigError("Invalid OpenSSH public key.")
    return value


def outputs(config: dict, root: Path = ROOT) -> dict[str, str]:
    """Explicit allowlists prevent secrets entering public inputs or Terraform."""
    validate(config, config["target"], root)
    vm = config["vm"]
    host = {
        **config["host"],
        **{key: vm[key] for key in ("ssh_public_key", "ssh_private_key")},
        "name": vm["name"],
        "target": config["target"],
        "dns": config["dns"],
        "roles": config["roles"],
        "services": config["services"],
    }
    result = {"secrets.yaml": yaml.safe_dump(config["secrets"], sort_keys=False)}
    if config["target"] == "proxmox":
        pve = config["proxmox"]
        host.update(proxmox_host=pve["host"], proxmox_vmid=pve["vmid"], proxmox_username=vm["username"], proxmox_address=pve["address"])
        values = {dest: str(pve[source]) for source, dest in PVE_ENV.items()}
        values.update(VMNAME=vm["name"], USERNAME=vm["username"], EXPECTED_IPV4="" if pve["address"] == "auto" else pve["address"])
        result["ubuntu-cloud.env"] = "".join(f"{key}={value}\n" for key, value in values.items())
    else:
        variables = {
            **config["aws"],
            "bootstrap_mode": "external",
            "vm_name": vm["name"],
            "admin_user": vm["username"],
            "ssh_public_key": public_key(vm["ssh_public_key"]),
        }
        result["aws.tfvars.json"] = json.dumps(variables, indent=2) + "\n"
    result["host.yaml"] = yaml.safe_dump(host, sort_keys=False)
    return result


class Configuration:
    def __init__(self, root: Path, directory: Path, target: str):
        if target not in ("aws", "proxmox"):
            raise ConfigError("Select TARGET=aws or TARGET=proxmox explicitly.")
        self.root = root.resolve()
        self.directory = directory.absolute()
        config_root = self.root / "config"
        if not self.directory.resolve().is_relative_to(config_root.resolve()) or self.directory.resolve() == config_root.resolve():
            raise ConfigError("Select a deployment directory under ignored config/.")
        # Allow aliases above the repository, not symlinked paths within config/.
        # Use the outermost boundary so a config/ alias back to the root cannot
        # masquerade as a second repository boundary.
        repository = next((parent for parent in reversed(self.directory.parents) if parent.resolve() == self.root), self.root)
        # Refuse aliases into another deployment, even when still below config/.
        current = self.directory
        while current not in (repository, current.parent):
            if current.is_symlink():
                raise ConfigError("Refusing symlinked configuration paths.")
            current = current.parent
        self.directory = self.directory.resolve()
        self.target = target
        self.source = self.directory / "bootstrap.yaml"
        self.generated = self.directory / "generated"

    def load(self) -> dict:
        if not self.directory.is_dir() or stat.S_IMODE(self.directory.stat().st_mode) & 0o077:
            raise ConfigError("Deployment directory permissions must be private (0700).")
        config = read_yaml(self.source)
        validate(config, self.target, self.root)
        return config

    def init(self) -> None:
        private_directory(self.directory)
        if self.source.exists() or self.source.is_symlink():
            self.load()
            if self.target == "aws":
                self.detect_aws()
            return
        if any(self.directory.iterdir()):
            raise ConfigError(
                "Deployment directory is not empty. Restore its original bootstrap.yaml or select an empty directory for a new deployment."
            )
        template = (self.root / f"config-example/bootstrap-{self.target}.yaml").read_text()
        selected = os.environ.get("BOOTSTRAP_SSH_PUBLIC_KEY", "")
        if selected:
            if not selected.endswith(".pub"):
                raise ConfigError("BOOTSTRAP_SSH_PUBLIC_KEY must select a .pub file.")
            template = template.replace("~/.ssh/id_ed25519.pub", json.dumps(selected)).replace(
                "~/.ssh/id_ed25519\n", json.dumps(selected[:-4]) + "\n"
            )
        write_private(self.source, template)
        if self.target == "aws":
            self.detect_aws()

    def detect_aws(self) -> None:
        config = self.load()
        aws = config["aws"]
        updates = {}
        if aws["expected_account_id"] == "123456789012":
            result = subprocess.run(  # noqa: S603 -- resolved executable and fixed read-only AWS arguments
                [executable("aws"), "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode or not re.fullmatch(r"[0-9]{12}", result.stdout.strip()):
                raise ConfigError("AWS account detection failed. Correct the approved credential chain, then rerun init.")
            updates["expected_account_id"] = result.stdout.strip()
        if aws["admin_source_address"] == "203.0.113.10/32":
            result = subprocess.run(  # noqa: S603 -- resolved executable and fixed public-IP endpoint
                [executable("curl"), "--fail", "--silent", "--show-error", "--max-time", "15", "--noproxy", "*", "https://api4.ipify.org"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            try:
                address = ipaddress.IPv4Address(result.stdout.strip())
                valid = result.returncode == 0 and address.is_global
            except ValueError:
                valid = False
            if not valid:
                raise ConfigError("Controller public IPv4 detection failed. Correct networking, then rerun init.")
            updates["admin_source_address"] = str(address) + "/32"
        if updates:
            public_key(config["vm"]["ssh_public_key"])
            text = self.source.read_text()
            for field, after in updates.items():
                # Preserve comments and all unrelated operator values, including secrets.
                pattern = rf"(?m)^([ \t]+{field}:[ \t]*)[^\n#]+"
                text, count = re.subn(pattern, lambda match, value=after: match[1] + json.dumps(value) + " ", text)
                if count != 1:
                    raise ConfigError("AWS detection requires one block-style field; edit the account/CIDR privately instead.")
            write_private(self.source, text)

    def prepare(self) -> str:
        config = self.load()
        rendered = outputs(config, self.root)
        private_directory(self.generated)
        # Validate all destinations before updating any; never touch deployment state.
        for name in rendered:
            path = self.generated / name
            if path.exists() or path.is_symlink():
                regular(path)
        for name, content in rendered.items():
            write_private(self.generated / name, content)
        return hashlib.sha256(json.dumps(rendered, sort_keys=True).encode()).hexdigest()

    def show(self) -> dict:
        config = self.load()
        endpoints = config["dns"].get("adguard_urls", [config["dns"]["adguard_url"]] if "adguard_url" in config["dns"] else [])
        return {
            "target": self.target,
            "name": config["vm"]["name"],
            "domain": config["host"].get("domain"),
            "repository_ref": config["host"].get("repository_ref"),
            "docker_volumes": config["host"].get("docker_volumes"),
            "roles": config["roles"],
            "services": config["services"],
            "proxmox_host": config.get("proxmox", {}).get("host"),
            "proxmox_vmid": config.get("proxmox", {}).get("vmid"),
            "adguard_hosts": [urlsplit(url).hostname for url in endpoints],
            "secrets": "Omitted. The source is private; never share it with an agent.",
        }

    def run(self, action: str) -> int:
        if action not in ACTIONS:
            raise ConfigError("Unsupported bootstrap action.")
        if action.startswith("vm-") and self.target != "proxmox":
            raise ConfigError("VM helpers require the Proxmox target.")
        if action.startswith("destroy") and self.target != "aws":
            raise ConfigError("Automated destruction supports only AWS.")
        digest = self.prepare()
        plan_kind = "destroy" if action.startswith("destroy") else "apply"
        plan = self.directory / ("destroy.tfplan" if plan_kind == "destroy" else "aws.tfplan")
        receipt = self.directory / f"{plan_kind}-inputs.json"
        planning = self.target == "aws" and action in ("plan", "destroy-plan")
        if self.target == "aws" and action in ("apply", "destroy"):
            regular(receipt)
            expected = json.loads(receipt.read_text())
            regular(plan)
            if expected != {"inputs": digest, "plan": hashlib.sha256(plan.read_bytes()).hexdigest()}:
                raise ConfigError("Inputs or saved plan changed since review. Run and review a new plan before applying.")
        if planning:
            receipt.unlink(missing_ok=True)
        # Task gives process environment precedence over dotenv. The source, not an
        # unrelated exported VMID/host, must select the VM for this deployment.
        inherited = {key: value for key, value in os.environ.items() if key not in set(PVE_ENV.values()) | {"VMNAME", "USERNAME", "EXPECTED_IPV4"}}
        env = {**inherited, "BOOTSTRAP_INPUT_DIR": str(self.generated), "BOOTSTRAP_PREPARED": "1"}
        # Native tools must create private plans/state, regardless of controller defaults.
        previous_umask = os.umask(0o077)
        try:
            result = subprocess.run(  # noqa: S603 -- fixed action allowlist; configuration paths are not shell-expanded
                [
                    executable("task"),
                    "bootstrap:native",
                    f"ACTION={action}",
                    f"TARGET={self.target}",
                    f"BOOTSTRAP_CONFIG_DIR={self.directory.relative_to(self.root)}",
                ],
                cwd=self.root,
                env=env,
                check=False,
            )
        finally:
            os.umask(previous_umask)
        if result.returncode == 0 and planning:
            if digest != hashlib.sha256(json.dumps(outputs(self.load(), self.root), sort_keys=True).encode()).hexdigest():
                raise ConfigError("Inputs changed during planning. Review a new plan; this plan is not approved for apply.")
            regular(plan)
            write_private(receipt, json.dumps({"inputs": digest, "plan": hashlib.sha256(plan.read_bytes()).hexdigest()}) + "\n")
        return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "show-config", "prepare", *ACTIONS))
    args = parser.parse_args()
    try:
        target = os.environ.get("BOOTSTRAP_TARGET", "")
        directory = Path(os.environ.get("BOOTSTRAP_DIR", ROOT / f"config/bootstrap-{target}"))
        config = Configuration(ROOT, directory, target)
        if args.command == "init":
            config.init()
        elif args.command == "show-config":
            print(yaml.safe_dump(config.show(), sort_keys=False), end="")
        elif args.command == "prepare":
            config.prepare()
        else:
            return config.run(args.command)
    except ConfigError as error:
        print(f"Bootstrap configuration: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print(
            "Bootstrap configuration failed. Check private file permissions, required fields and controller prerequisites; no private values are displayed.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
