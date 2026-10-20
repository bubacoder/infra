"""Read-only, bounded bootstrap progress checks; never print provider/guest output."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
from pathlib import Path

if __package__:
    from scripts.bootstrap_config import ROOT, Configuration, executable, regular
else:
    from bootstrap_config import ROOT, Configuration, executable, regular


class StatusError(Exception):
    """A public diagnostic containing no private command output."""


def command(argv: list[str], *, timeout: int = 20, env: dict | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env, check=False)  # noqa: S603 -- fixed arguments, no shell
    except (OSError, subprocess.TimeoutExpired) as error:
        raise StatusError("A status check timed out or its executable is unavailable.") from error


def parsed(result: subprocess.CompletedProcess) -> dict | list:
    try:
        value = json.loads(result.stdout)
    except (ValueError, TypeError) as error:
        raise StatusError("The provider returned an invalid status response.") from error
    if not isinstance(value, (dict, list)):
        raise StatusError("The provider returned an invalid status response.")
    return value


def ssh_status(host: str, argv: list[str]) -> subprocess.CompletedProcess:
    return command([executable("ssh"), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=5", host, *argv])


def guest_status(config: dict, directory: Path, address: str, *, cloud_init: bool = True) -> None:
    try:
        ipaddress.IPv4Address(address)
    except ValueError as error:
        raise StatusError("Provider returned an invalid guest address.") from error
    trust = directory / "known_hosts"
    if not trust.exists() and not trust.is_symlink():
        print("Guest SSH: not yet pinned; run bootstrap:apply or bootstrap:configure after provisioning")
        return
    regular(trust)
    found = command([executable("ssh-keygen"), "-F", address, "-f", str(trust)])
    if found.returncode == 1:
        print("Guest SSH: no pinned key for current address; bootstrap must establish trust")
        return
    if found.returncode:
        raise StatusError("Cannot inspect the deployment's pinned SSH key.")
    vm = config["vm"]
    ssh = [
        executable("ssh"),
        "-i",
        str(Path(vm["ssh_private_key"]).expanduser()),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        f"UserKnownHostsFile={trust}",
        f"{vm['username']}@{address}",
    ]
    cloud = command([*ssh, "cloud-init", "status"])
    if cloud.returncode == 255:
        print("Guest SSH: unavailable or pinned host key rejected; no trust changes made")
        return
    print(
        "Guest SSH: connected with pinned key"
        if cloud.stdout.strip() in ("status: done", "status: running", "status: error", "status: disabled")
        else "Guest SSH: reachable; cloud-init status unavailable"
    )
    if cloud_init:
        print(
            f"Cloud-init: {cloud.stdout.strip() if cloud.stdout.strip() in ('status: done', 'status: running', 'status: error', 'status: disabled') else 'unknown'}"
        )
    if "k3s" not in config["roles"]:
        return
    service = command([*ssh, "sudo", "-n", "systemctl", "is-active", "k3s"])
    active = service.stdout.strip() if service.stdout.strip() in ("active", "inactive", "failed", "activating", "deactivating") else "unavailable"
    print(f"K3s service: {active}")
    if active != "active":
        return
    node = command([*ssh, "sudo", "-n", "/usr/local/bin/k3s", "kubectl", "get", "node", vm["name"], "-o", "json", "--request-timeout=10s"])
    ready = "unavailable"
    if node.returncode == 0:
        data = parsed(node)
        if isinstance(data, dict):
            node_status = data.get("status")
            conditions = node_status.get("conditions", []) if isinstance(node_status, dict) else []
            if isinstance(conditions, list):
                ready = next(
                    (
                        item.get("status")
                        for item in conditions
                        if isinstance(item, dict) and item.get("type") == "Ready" and item.get("status") in ("True", "False", "Unknown")
                    ),
                    "unavailable",
                )
    print(f"K3s node Ready: {ready}")


def proxmox_status(config: dict, directory: Path) -> None:
    pve = config["proxmox"]
    vmid = str(pve["vmid"])
    host = pve["host"]
    result = ssh_status(host, ["sudo", "-n", "qm", "status", vmid])
    if result.returncode:
        if "does not exist" in result.stderr or "does not exist" in result.stdout:
            print(f"Proxmox VM {vmid}: absent")
            return
        raise StatusError("Cannot read Proxmox VM status; check trusted access and VM ID.")
    match = re.fullmatch(r"status: (running|stopped|paused|suspended|prelaunch)", result.stdout.strip())
    if not match:
        raise StatusError("Proxmox returned an unrecognized VM status.")
    state = match[1]
    # Never describe an unrelated VM as this deployment.
    identity = ssh_status(host, ["sudo", "-n", "qm", "config", vmid, "--current", "1"])
    config_lines = identity.stdout.splitlines()
    disk = next((line for line in config_lines if line.startswith("scsi0: ")), "")
    snippet = next((line for line in config_lines if line.startswith("cicustom: ")), "")
    if (
        identity.returncode
        or f"name: {config['vm']['name']}" not in config_lines
        or f"ciuser: {config['vm']['username']}" not in config_lines
        or f"vm-{vmid}-disk-" not in disk
        or f"-{vmid}-cloud-user.yaml" not in snippet
    ):
        raise StatusError("VM ID exists but identity does not match this deployment; inspect the hypervisor.")
    print(f"Proxmox VM {vmid} ({config['vm']['name']}): {state}")
    if state != "running":
        return
    interfaces = ssh_status(host, ["sudo", "-n", "qm", "guest", "cmd", vmid, "network-get-interfaces"])
    if interfaces.returncode:
        print("Guest agent: not ready")
        return
    data = parsed(interfaces)
    nics = data.get("result", data) if isinstance(data, dict) else data
    mac_match = re.search(r"virtio=([0-9a-f:]{17})", next((line for line in config_lines if line.startswith("net0: ")), ""), re.I)
    if not mac_match or not isinstance(nics, list):
        raise StatusError("Cannot establish the VM's primary network identity.")
    addresses = {
        ip.get("ip-address")
        for nic in nics
        if isinstance(nic, dict) and nic.get("hardware-address", "").lower() == mac_match[1].lower()
        for ip in nic.get("ip-addresses", [])
        if isinstance(ip, dict)
        and ip.get("ip-address-type") == "ipv4"
        and isinstance(ip.get("ip-address"), str)
        and not ip["ip-address"].startswith(("127.", "0."))
    }
    if len(addresses) != 1:
        print("Guest agent: ready; primary IPv4 not uniquely available")
        return
    address = addresses.pop()
    try:
        ipaddress.IPv4Address(address)
    except ValueError as error:
        raise StatusError("Guest agent returned an invalid IPv4 address.") from error
    print(f"Guest agent: ready; primary IPv4: {address}")
    if pve["address"] != "auto" and pve["address"] != address:
        raise StatusError("Guest address differs from the deployment's reserved address.")
    # The guest agent executes only a read-only command; no credentials or cloud-init logs.
    cloud = ssh_status(host, ["sudo", "-n", "qm", "guest", "exec", vmid, "--timeout", "10", "--", "cloud-init", "status"])
    if cloud.returncode:
        print("Cloud-init: not yet queryable through guest agent")
        return
    status = parsed(cloud)
    if not isinstance(status, dict) or status.get("exitcode") != 0:
        print("Cloud-init: not yet queryable through guest agent")
        return
    text = status.get("out-data", "").strip()
    print(f"Cloud-init (guest agent): {text if text in ('status: done', 'status: running', 'status: error', 'status: disabled') else 'unknown'}")
    if text == "status: done":
        guest_status(config, directory, address, cloud_init=False)


def aws_status(config: dict, directory: Path) -> None:
    aws = config["aws"]
    if not (directory / "aws.tfstate").exists() and not (directory / "aws.tfstate").is_symlink():
        print("AWS deployment: no local Terraform state in the selected directory")
        return
    regular(directory / "aws.tfstate")
    identity = command([executable("aws"), "sts", "get-caller-identity", "--query", "Account", "--output", "text"])
    if identity.returncode or identity.stdout.strip() != aws["expected_account_id"]:
        raise StatusError("AWS account check failed or does not match this deployment; no resources queried.")
    env = {**os.environ, "TF_DATA_DIR": str(directory / ".terraform")}
    # Explicitly bind both read-only commands to this deployment's local backend;
    # an uninitialized .terraform directory must never fall back to another state.
    state = f"-state={directory / 'aws.tfstate'}"
    output = command([executable("terraform"), f"-chdir={ROOT / 'terraform/aws-vm'}", "output", state, "-json", "bootstrap_host"], env=env)
    if output.returncode:
        resources = command([executable("terraform"), f"-chdir={ROOT / 'terraform/aws-vm'}", "state", "list", state], env=env)
        if resources.returncode == 0 and not resources.stdout.strip():
            print("AWS deployment: no managed resources in the selected Terraform state")
            return
        raise StatusError("Cannot read the deployment's non-secret Terraform bootstrap_host output; use the original backend.")
    data = parsed(output)
    if (
        not isinstance(data, dict)
        or data.get("name") != config["vm"]["name"]
        or data.get("account_id") != aws["expected_account_id"]
        or data.get("region") != aws["aws_region"]
    ):
        raise StatusError("Terraform output does not identify the selected deployment.")
    instance = data.get("instance_id", "")
    if not isinstance(instance, str) or not re.fullmatch(r"i-[0-9a-f]+", instance):
        raise StatusError("Terraform output has no valid EC2 instance ID.")
    result = command(
        [
            executable("aws"),
            "--region",
            aws["aws_region"],
            "ec2",
            "describe-instances",
            "--instance-ids",
            instance,
            "--query",
            "Reservations[].Instances[].State.Name",
            "--output",
            "json",
        ]
    )
    if result.returncode:
        raise StatusError("Cannot read EC2 instance status; check account, region and API access.")
    states = parsed(result)
    if (
        not isinstance(states, list)
        or len(states) != 1
        or states[0] not in ("running", "stopped", "pending", "stopping", "shutting-down", "terminated")
    ):
        raise StatusError("EC2 returned an unexpected instance identity or state.")
    print(f"AWS instance {instance} ({config['vm']['name']}): {states[0]}")
    if states[0] != "running":
        return
    online = command(
        [
            executable("aws"),
            "--region",
            aws["aws_region"],
            "ssm",
            "describe-instance-information",
            "--filters",
            f"Key=InstanceIds,Values={instance}",
            "--query",
            "InstanceInformationList[].PingStatus",
            "--output",
            "json",
        ]
    )
    if online.returncode:
        print("SSM: unavailable")
    else:
        pings = parsed(online)
        print(
            f"SSM: {pings[0] if isinstance(pings, list) and len(pings) == 1 and pings[0] in ('Online', 'ConnectionLost', 'Inactive') else 'not registered'}"
        )
    if isinstance(data.get("address"), str) and data["address"]:
        guest_status(config, directory, data["address"])
    else:
        print("Guest address: not yet available")


def status(configuration: Configuration) -> None:
    config = configuration.load()  # Validate privately without generating inputs or changing receipts.
    if configuration.target == "proxmox":
        proxmox_status(config, configuration.directory)
    else:
        aws_status(config, configuration.directory)
