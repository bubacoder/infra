"""Guarded Proxmox bootstrap teardown. No private input or guest data is printed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

if __package__:
    from scripts.bootstrap.config import ROOT, ConfigError, Configuration, executable, read_yaml, regular, write_private
else:
    from config import ROOT, ConfigError, Configuration, executable, read_yaml, regular, write_private


class DestroyError(Exception):
    """An operator-safe teardown failure."""


def remote(host: str, *args: str, allow_missing: bool = False, allow_absent: bool = False) -> str | None:
    try:
        result = subprocess.run(  # noqa: S603 -- validated host and fixed native command arguments
            [executable("ssh"), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", host, "env", "LC_ALL=C", "LANG=C", "sudo", "-n", *args],
            capture_output=True,
            text=True,
            timeout=180 if args[:2] in (("qm", "shutdown"), ("qm", "destroy")) else 35,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise DestroyError("Cannot reach the trusted Proxmox host or complete its native command.") from error
    if result.returncode:
        if allow_absent and args[:2] == ("test", "-e") and result.returncode == 1:
            return None
        if (
            allow_missing
            and "does not exist" in result.stderr
            and ("Configuration file 'nodes/" in result.stderr or "Configuration file does not exist" in result.stderr)
        ):
            return None
        raise DestroyError("Proxmox rejected a guarded teardown check or operation; preserve the plan and inspect the host.")
    return result.stdout.strip()


def native_json(host: str, path: str, *, allow_missing: bool = False) -> dict | list | None:
    raw = remote(host, "pvesh", "get", path, "--output-format", "json", allow_missing=allow_missing)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError as error:
        raise DestroyError("Proxmox returned invalid JSON; no destruction was attempted.") from error


def volumes(host: str, storage: str, vmid: int) -> list[tuple[str, str]]:
    data = remote(host, "pvesm", "list", storage, "--vmid", str(vmid))
    lines = data.splitlines()
    if not lines or not lines[0].startswith("Volid"):
        raise DestroyError("Proxmox storage inventory is incomplete; preserve the VM and recovery records.")
    result = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 4 or not parts[0].startswith(storage + ":"):
            raise DestroyError("Proxmox returned an ambiguous volume entry; preserve storage data.")
        result.append((parts[0], parts[2]))
    return result


def inventory(host: str, vmid: int) -> tuple[list[str], list[tuple[str, str]]]:
    data = remote(host, "pvesm", "status")
    lines = data.splitlines()
    if not lines or not lines[0].startswith("Name"):
        raise DestroyError("Proxmox storage status is unavailable.")
    entries = [line.split() for line in lines[1:]]
    if any(len(parts) < 3 or parts[2] != "active" for parts in entries):
        raise DestroyError("A configured Proxmox storage is inactive or ambiguous; owned data cannot be ruled out.")
    storages = [parts[0] for parts in entries]
    if not storages:
        raise DestroyError("No active Proxmox storage is available for ownership checks.")
    return storages, [volume for storage in storages for volume in volumes(host, storage, vmid)]


def identity(config: dict, vm: dict) -> dict:
    vmid = config["proxmox_vmid"]
    name = config["name"]
    storage = config["proxmox_storage"]
    if vm.get("name") != name or vm.get("ciuser") != config["proxmox_username"] or vm.get("protection") or vm.get("lock"):
        raise DestroyError("VM identity, protection or lock does not match the selected deployment.")
    disk = str(vm.get("scsi0", "")).split(",", 1)[0]
    cloudinit = str(vm.get("ide2", "")).split(",", 1)[0]
    if disk != f"{storage}:vm-{vmid}-disk-0" or cloudinit != f"{storage}:vm-{vmid}-cloudinit":
        raise DestroyError("VM disks do not match the selected deployment; inspect ownership before teardown.")
    custom = vm.get("cicustom", "")
    match = re.fullmatch(
        rf"user=local:snippets/(ubuntu-[0-9.]+-{vmid}-cloud-user\.yaml),network=local:snippets/(ubuntu-[0-9.]+-{vmid}-cloud-network\.yaml)",
        custom,
    )
    if not match:
        raise DestroyError("VM cloud-init snippets are not unambiguously owned by this deployment.")
    return {
        "name": name,
        "vmid": vmid,
        "config_hash": hashlib.sha256(json.dumps(vm, sort_keys=True).encode()).hexdigest(),
        "volumes": [disk, cloudinit],
        "snippets": list(match.groups()),
    }


def snippet_digest(host: str, snippet: str, *, optional: bool = False) -> str | None:
    path = f"/var/lib/vz/snippets/{snippet}"
    if remote(host, "test", "-e", path, allow_absent=True) is None:
        if optional:
            return None
        raise DestroyError("An owned cloud-init snippet is missing; do not destroy an ambiguous VM.")
    remote(host, "test", "-f", path)
    remote(host, "test", "!", "-L", path)
    checksum = remote(host, "sha256sum", "--", path)
    if not re.fullmatch(rf"[0-9a-f]{{64}}  {re.escape(path)}", checksum):
        raise DestroyError("Cannot verify the owned cloud-init snippet fingerprint.")
    return checksum[:64]


def inspect(config: dict, *, resolve_address: bool = True) -> dict:
    host, vmid = config["proxmox_host"], config["proxmox_vmid"]
    node = remote(host, "hostname")
    if not re.fullmatch(r"[a-zA-Z0-9-]+", node):
        raise DestroyError("Proxmox node identity is invalid.")
    vm = native_json(host, f"/nodes/{node}/qemu/{vmid}/config", allow_missing=True)
    if vm is None:
        raise DestroyError("VM is absent; preserve the plan and use destroy-cleanup only after a reviewed destroy.")
    if not isinstance(vm, dict):
        raise DestroyError("Proxmox VM configuration is invalid.")
    entry = identity(config, vm)
    entry["snippet_hashes"] = {snippet: snippet_digest(host, snippet) for snippet in entry["snippets"]}
    entry["node"] = node
    snapshots = native_json(host, f"/nodes/{node}/qemu/{vmid}/snapshot")
    if not isinstance(snapshots, list) or any(not isinstance(item, dict) or item.get("name") != "current" for item in snapshots):
        raise DestroyError("VM snapshots or uncertain snapshot state exist; preserve recovery data.")
    storages, found = inventory(host, vmid)
    if any(kind == "backup" for _, kind in found):
        raise DestroyError("Owned backups exist on Proxmox storage; retain them and review teardown separately.")
    if sorted(vol for vol, kind in found if kind == "images") != sorted(entry["volumes"]):
        raise DestroyError("Owned disk inventory differs from the VM config; do not delete unreferenced or foreign data.")
    if entry["volumes"][0].split(":", 1)[0] not in storages:
        raise DestroyError("Selected VM storage is not active.")
    entry["storages"] = storages
    entry["status"] = remote(host, "qm", "status", str(vmid))
    if entry["status"] not in ("status: running", "status: stopped"):
        raise DestroyError("VM is not in a stable running or stopped state.")
    address = config["proxmox_address"]
    if address == "auto" and config["dns"]["enabled"] and resolve_address:
        if entry["status"] != "status: running":
            raise DestroyError("DNS teardown requires a running guest agent or an explicit reserved VM address.")
        interfaces = json.loads(remote(host, "qm", "guest", "cmd", str(vmid), "network-get-interfaces"))
        nics = interfaces.get("result", interfaces) if isinstance(interfaces, dict) else interfaces
        mac = re.search(r"virtio=([0-9a-f:]{17})", vm.get("net0", ""), re.I)
        if not mac or not isinstance(nics, list):
            raise DestroyError("Cannot bind DNS cleanup to the guest's original NIC.")
        addresses = {
            ip.get("ip-address")
            for nic in nics
            if nic.get("hardware-address", "").lower() == mac[1].lower()
            for ip in nic.get("ip-addresses", [])
            if ip.get("ip-address-type") == "ipv4" and not ip.get("ip-address", "").startswith(("127.", "0."))
        }
        if len(addresses) != 1:
            raise DestroyError("Guest agent returned ambiguous DNS address ownership.")
        address = addresses.pop()
    entry["address"] = "" if address == "auto" else address
    return entry


def plan_path(directory: Path) -> Path:
    return directory / "proxmox-destroy-plan.json"


def plan(config: dict, directory: Path) -> None:
    if os.environ.get("BOOTSTRAP_DELETE_DATA") != "1":
        raise DestroyError("Explicit DELETE_DATA=1 is required to review destructive VM removal.")
    dns_receipt = directory / "dns-state.yaml"
    if dns_receipt.exists() or dns_receipt.is_symlink():
        owned_dns = read_yaml(dns_receipt)
        if owned_dns.get("records") and not config["dns"]["enabled"]:
            raise DestroyError("Owned DNS records remain; restore the original DNS settings before reviewing VM removal.")
    selected = inspect(config)
    # Source and generated credentials never enter the reviewed plan.
    plan_file = plan_path(directory)
    write_private(plan_file, json.dumps(selected, sort_keys=True) + "\n")
    print(
        f"Review Proxmox VM {selected['vmid']} ({selected['name']}) on {selected['node']}: {selected['status']}; 2 owned disks, 2 cloud-init snippets, no snapshots/backups."
    )


def approved(config: dict, directory: Path) -> dict:
    path = plan_path(directory)
    regular(path)
    try:
        approved_plan = json.loads(path.read_text())
    except (ValueError, UnicodeError) as error:
        raise DestroyError("Reviewed Proxmox destroy plan is invalid.") from error
    if not isinstance(approved_plan, dict) or approved_plan.get("vmid") != config["proxmox_vmid"] or approved_plan.get("name") != config["name"]:
        raise DestroyError("Reviewed Proxmox plan does not match the deployment.")
    return approved_plan


def destroy(config: dict, directory: Path) -> None:
    expected = approved(config, directory)
    current = inspect(config)
    if {key: value for key, value in current.items() if key != "status"} != {key: value for key, value in expected.items() if key != "status"}:
        raise DestroyError("Proxmox VM changed since review; run and review a new destroy-plan.")
    host, vmid = config["proxmox_host"], str(config["proxmox_vmid"])
    if current["status"] == "status: running":
        remote(host, "qm", "shutdown", vmid, "--timeout", "120")
    if remote(host, "qm", "status", vmid) != "status: stopped" or inspect(config, resolve_address=False)["config_hash"] != expected["config_hash"]:
        raise DestroyError("VM did not shut down cleanly or changed during shutdown; preserve the plan.")
    remote(host, "qm", "destroy", vmid, "--purge", "1")
    print(f"Destroyed reviewed Proxmox VM {vmid}; run the guarded cleanup checks.")


def cleanup(config: dict, directory: Path) -> None:
    expected = approved(config, directory)
    host, vmid = config["proxmox_host"], config["proxmox_vmid"]
    node = remote(host, "hostname")
    if node != expected["node"]:
        raise DestroyError("Proxmox node identity changed; preserve recovery records.")
    if native_json(host, f"/nodes/{node}/qemu/{vmid}/config", allow_missing=True) is not None:
        raise DestroyError("VM still exists; do not remove deployment-owned artifacts.")
    for storage in inventory(host, vmid)[0]:
        if any(kind != "snippets" for _, kind in volumes(host, storage, vmid)):
            raise DestroyError("VM disks or backups remain; preserve recovery records.")
    for snippet in expected["snippets"]:
        found = snippet_digest(host, snippet, optional=True)
        if found is not None and found != expected["snippet_hashes"][snippet]:
            raise DestroyError("An owned cloud-init snippet changed after review; preserve it.")
    for snippet in expected["snippets"]:
        if snippet_digest(host, snippet, optional=True) is not None:
            remote(host, "rm", "--", f"/var/lib/vz/snippets/{snippet}")
    print(f"Verified Proxmox VM {vmid} absent; removed only its reviewed cloud-init snippets.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "destroy", "cleanup"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if os.environ.get("BOOTSTRAP_PREPARED") != "1":
            raise DestroyError("Use the public bootstrap command to prepare and validate this deployment.")  # noqa: TRY301 -- entrypoint guard
        selected = Configuration(ROOT, args.directory, "proxmox")
        source = selected.load()
        directory = selected.directory
        config = read_yaml(directory / "generated/host.yaml")
        if (
            config.get("target") != "proxmox"
            or config.get("name") != source["vm"]["name"]
            or config.get("proxmox_vmid") != source["proxmox"]["vmid"]
            or config.get("proxmox_host") != source["proxmox"]["host"]
            or config.get("proxmox_storage") != source["proxmox"]["storage"]
        ):
            raise DestroyError("Generated inputs do not match the private deployment source.")  # noqa: TRY301 -- entrypoint guard
        {"plan": plan, "destroy": destroy, "cleanup": cleanup}[args.action](config, directory)
    except (DestroyError, ConfigError, OSError, ValueError, KeyError, TypeError):
        print(
            "Proxmox teardown stopped: verify reviewed VM identity, disk ownership, snapshots and recovery records; no private values are displayed.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
