"""Proxmox VM planning, preflight, provisioning, and SSH trust."""

import hashlib
import ipaddress
import json
import shlex
import shutil
import socket
from dataclasses import asdict, replace

import yaml

from .config import detect_repository
from .core import ROOT, BootstrapConfig, BootstrapError, BootstrapPlan, Runner, remote, task, vm_ssh_command


def generated_mac(target: str, vm_name: str) -> str:
    """Derive a stable, locally administered unicast MAC address for a VM."""
    digest = hashlib.sha256(f"{target}\0{vm_name}".encode()).digest()
    return ":".join(f"{octet:02X}" for octet in [0x02, digest[0], digest[1], digest[2], digest[3], digest[4]])


def proxmox_vm_rows(config: BootstrapConfig, runner: Runner) -> list[tuple[int, str]]:
    """Return VM ID and name pairs reported by the configured Proxmox host."""
    output = remote(runner, config.proxmox.ssh_target, "sudo qm list", capture=True)
    return [(int(fields[0]), fields[1]) for line in output.splitlines()[1:] if len(fields := line.split()) >= 2 and fields[0].isdigit()]


def resolve_plan(config: BootstrapConfig, runner: Runner, root=ROOT) -> BootstrapPlan:
    """Resolve repository and VM identity into a resumable bootstrap plan."""
    repository, rows = detect_repository(config, runner, root), proxmox_vm_rows(config, runner)
    named = next((vm_id for vm_id, name in rows if name == config.vm.name), None)
    if config.vm.vm_id == "auto":
        vm_id = named
        if vm_id is None:
            try:
                vm_id = int(remote(runner, config.proxmox.ssh_target, "sudo pvesh get /cluster/nextid", capture=True))
            except ValueError as error:
                raise BootstrapError("Proxmox returned an invalid next VM ID") from error
    else:
        vm_id = int(config.vm.vm_id)
        if named is not None and named != vm_id:
            raise BootstrapError(f"VM name {config.vm.name} already belongs to VM ID {named}")
    vm_exists = any(existing_id == vm_id for existing_id, _ in rows)
    if vm_exists and named != vm_id:
        raise BootstrapError(f"VM ID {vm_id} already exists with another name")
    return BootstrapPlan(config, repository, vm_id, config.vm.mac or generated_mac(config.proxmox.ssh_target, config.vm.name), vm_exists)


def print_plan(plan: BootstrapPlan) -> None:
    """Print the bootstrap plan as YAML with the TLS token redacted."""
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
        "network": {**asdict(plan.config.network), "expected_ipv4": plan.config.network.expected_ipv4 or "auto"},
        "host": asdict(plan.config.host),
        "tls": {"provider": plan.config.tls.provider, "acme_email": plan.config.tls.acme_email, "token": "<redacted>"},
    }
    print(yaml.safe_dump(summary, sort_keys=False).rstrip())


def verify_dns(plan: BootstrapPlan, expected: str, *, discovered: bool = False) -> None:
    """Require the base and bootstrap service names to resolve only to expected."""
    names = [
        plan.config.network.domain,
        f"traefik.{plan.config.network.domain}",
        f"home.{plan.config.network.domain}",
        f"bootstrap-check.{plan.config.network.domain}",
    ]
    failures: list[str] = []
    for name in names:
        try:
            addresses = {entry[4][0] for entry in socket.getaddrinfo(name, None, socket.AF_INET)}
        except socket.gaierror:
            addresses = set()
        if addresses != {expected}:
            failures.append(name)
    if not failures:
        return
    if discovered:
        raise BootstrapError(
            f"Networking checkpoint: VM {plan.vm_id} was discovered at {expected}. Ask the operator to map its base domain and service names to that address, then rerun bootstrap. Required names: {', '.join(names)}"
        )
    raise BootstrapError(
        f"External DHCP/DNS checkpoint is incomplete. Reserve {plan.mac} as {expected}, then point the base domain and wildcard to that address. Failed names: {', '.join(failures)}"
    )


def discover_vm_ipv4(plan: BootstrapPlan, runner: Runner) -> str:
    """Return the sole usable IPv4 address reported for the planned VM interface."""
    output = remote(runner, plan.config.proxmox.ssh_target, f"sudo qm guest cmd {plan.vm_id} network-get-interfaces", capture=True)
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
        raise BootstrapError(
            f"Expected exactly one usable IPv4 address on VM {plan.vm_id} interface {plan.mac}; found: {', '.join(sorted(addresses)) or 'none'}"
        )
    return addresses.pop()


def with_expected_ipv4(plan: BootstrapPlan, expected_ipv4: str) -> BootstrapPlan:
    """Return a copy of the plan bound to the given expected IPv4 address."""
    return replace(plan, config=replace(plan.config, network=replace(plan.config.network, expected_ipv4=expected_ipv4)))


def verify_existing_vm(plan: BootstrapPlan, runner: Runner) -> None:
    """Require an existing planned VM to match the resumable configuration."""
    if not plan.vm_exists:
        return
    output = remote(runner, plan.config.proxmox.ssh_target, f"sudo qm config {plan.vm_id}", capture=True)
    fields = dict(line.split(": ", 1) for line in output.splitlines() if ": " in line)

    def options(value: str) -> dict[str, str]:
        """Parse comma-delimited key-value options."""
        return dict(part.split("=", 1) for part in value.split(",") if "=" in part)

    network, agent, cloud_init = options(fields.get("net0", "")), options(fields.get("agent", "")), options(fields.get("cicustom", ""))
    disk = fields.get("scsi0", "").split(",", 1)[0]
    cloud_init_drive = fields.get("ide2", "").split(",", 1)[0]
    expected_user_data = f"local:snippets/ubuntu-{plan.config.vm.ubuntu_version}-{plan.vm_id}-cloud-user.yaml"
    expected_network_data = f"local:snippets/ubuntu-{plan.config.vm.ubuntu_version}-{plan.vm_id}-cloud-network.yaml"
    matches = (
        fields.get("name") == plan.config.vm.name
        and network.get("virtio", "").upper() == plan.mac
        and network.get("bridge") == plan.config.vm.bridge
        and disk == f"{plan.config.vm.storage}:vm-{plan.vm_id}-disk-0"
        and cloud_init_drive == f"{plan.config.vm.storage}:vm-{plan.vm_id}-cloudinit"
        and agent.get("enabled") == "1"
        and fields.get("ciuser") == plan.config.vm.username
        and cloud_init.get("user") == expected_user_data
        and cloud_init.get("network") == expected_network_data
    )
    if not matches:
        raise BootstrapError(
            f"Existing VM {plan.vm_id} is incomplete or does not match the expected name, MAC, disks, agent, and cloud-init configuration; inspect it before retrying"
        )


def preflight(plan: BootstrapPlan, runner: Runner) -> None:
    """Validate local tools, existing VM state, Proxmox resources, and DNS."""
    for tool in ("git", "task", "ssh", "ssh-keyscan", "rsync", "ansible-playbook", "curl"):
        if shutil.which(tool) is None:
            raise BootstrapError(f"Required executable is not installed: {tool}")
    verify_existing_vm(plan, runner)
    target, storage, bridge = plan.config.proxmox.ssh_target, shlex.quote(plan.config.vm.storage), shlex.quote(plan.config.vm.bridge)
    remote(runner, target, f"sudo pvesm status --storage {storage} >/dev/null")
    remote(runner, target, f"ip link show {bridge} >/dev/null")
    try:
        content = json.loads(remote(runner, target, "sudo pvesh get /storage/local --output-format json", capture=True))["content"].split(",")
    except (json.JSONDecodeError, KeyError, AttributeError) as error:
        raise BootstrapError("Could not read Proxmox storage 'local' configuration") from error
    if "snippets" not in content:
        raise BootstrapError("Proxmox storage 'local' must allow snippet content")
    if not plan.vm_exists:
        mac = shlex.quote(plan.mac)
        status = remote(
            runner,
            target,
            f"sudo grep -Riq -- {mac} /etc/pve/qemu-server; code=$?; if [ $code -eq 0 ]; then printf used; elif [ $code -eq 1 ]; then printf available; else exit $code; fi",
            capture=True,
        )
        if status != "available":
            raise BootstrapError(f"MAC address is already used: {plan.mac}")
    if plan.config.network.expected_ipv4:
        verify_dns(plan, plan.config.network.expected_ipv4)


def provision_vm(plan: BootstrapPlan, runner: Runner) -> None:
    """Resume an existing VM or run the VM preflight and provisioning tasks."""
    if plan.vm_exists:
        if "status: running" not in remote(runner, plan.config.proxmox.ssh_target, f"sudo qm status {plan.vm_id}", capture=True):
            remote(runner, plan.config.proxmox.ssh_target, f"sudo qm start {plan.vm_id}")
        task(runner, "bootstrap:vm-wait")
        return
    task(runner, "bootstrap:vm-preflight")
    task(runner, "bootstrap:vm-provision")


def establish_ssh_trust(plan: BootstrapPlan, runner: Runner) -> None:
    """Verify the VM's network SSH key against its guest-agent key and trust it."""
    guest_result = remote(
        runner, plan.config.proxmox.ssh_target, f"sudo qm guest exec {plan.vm_id} -- cat /etc/ssh/ssh_host_ed25519_key.pub", capture=True
    )
    try:
        guest_key = json.loads(guest_result)["out-data"].split()[1]
    except (KeyError, IndexError, json.JSONDecodeError) as error:
        raise BootstrapError("Could not read the VM SSH host key through the Proxmox guest agent") from error
    network_key = next(
        (
            fields[2]
            for line in runner.run(["ssh-keyscan", "-T", "10", "-t", "ed25519", plan.config.network.expected_ipv4], capture=True).splitlines()
            if len(fields := line.split()) == 3 and fields[1] == "ssh-ed25519"
        ),
        None,
    )
    if not network_key or network_key != guest_key:
        raise BootstrapError("The VM SSH host key does not match the key presented on the network")
    command = vm_ssh_command(plan, "true")
    command[1:1] = ["-o", "StrictHostKeyChecking=accept-new"]
    runner.run(command)
