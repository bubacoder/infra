"""Safely install and check a deployment-owned K3s context on the controller.

Admin kubeconfig travels on Ansible stdin, never through arguments or output.
All failures are operator-safe; do not print exception details or credential data.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import yaml

if __package__:
    from scripts.bootstrap.config import ROOT, ConfigError, executable, regular, write_private
else:
    from config import ROOT, ConfigError, executable, regular, write_private


class AccessError(Exception):
    """A diagnostic containing no admin credential material."""


def selected_directory(value: str) -> Path:
    path = Path(value).absolute()
    root = ROOT / "config"
    if not path.resolve().is_relative_to(root.resolve()) or path.resolve() == root.resolve():
        raise AccessError("Access requires the selected deployment directory under config/.")
    current = path
    while current not in (ROOT, current.parent):
        if current.is_symlink():
            raise AccessError("Refusing a symlinked deployment directory.")
        current = current.parent
    if not path.is_dir() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise AccessError("Deployment directory must have private permissions (0700).")
    return path


def kube_dir_for(home: Path) -> Path:
    path = home / ".kube"
    if path.is_symlink():
        raise AccessError("Refusing a symlinked ~/.kube directory.")
    if path.exists():
        if not path.is_dir() or stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise AccessError("Protect ~/.kube with mode 0700 before installing cluster-admin access.")
    else:
        path.mkdir(mode=0o700)
    return path


def existing(path: Path) -> bytes | None:
    if not path.exists() and not path.is_symlink():
        return None
    regular(path)
    return path.read_bytes()


def parse(raw: bytes) -> dict:
    try:
        value = yaml.safe_load(raw)
    except (yaml.YAMLError, UnicodeError) as error:
        raise AccessError("Invalid kubeconfig YAML; correct it privately.") from error
    if not isinstance(value, dict):
        raise AccessError("Kubeconfig must be a mapping.")
    for key in ("clusters", "users", "contexts"):
        if not isinstance(value.get(key), list):
            raise AccessError("Kubeconfig requires clusters, users and contexts lists.")
        if any(not isinstance(entry, dict) or not isinstance(entry.get("name"), str) for entry in value[key]):
            raise AccessError("Kubeconfig entries must have names.")
    return value


def renamed(raw: bytes, context: str, host: str) -> dict:
    value = parse(raw)
    if any(len(value[key]) != 1 for key in ("clusters", "users", "contexts")):
        raise AccessError("K3s admin kubeconfig must contain exactly one cluster, user and context.")
    cluster = value["clusters"][0]
    user = value["users"][0]
    entry = value["contexts"][0]
    if (
        not isinstance(entry.get("context"), dict)
        or entry["context"].get("cluster") != cluster["name"]
        or entry["context"].get("user") != user["name"]
    ):
        raise AccessError("K3s admin context does not reference its cluster and user.")
    if not isinstance(cluster.get("cluster"), dict) or not cluster["cluster"].get("certificate-authority-data"):
        raise AccessError("K3s admin kubeconfig is missing its TLS CA.")
    if cluster["cluster"].get("insecure-skip-tls-verify"):
        raise AccessError("K3s admin kubeconfig must require TLS verification.")
    if not isinstance(user.get("user"), dict) or not user["user"].get("client-certificate-data") or not user["user"].get("client-key-data"):
        raise AccessError("K3s admin kubeconfig is missing client credentials.")
    cluster["name"] = context
    cluster["cluster"]["server"] = f"https://{host}:6443"
    user["name"] = context
    entry["name"] = context
    entry["context"]["cluster"] = context
    entry["context"]["user"] = context
    value["current-context"] = context
    return value


def receipt_at(directory: Path) -> Path:
    return directory / "k3s-access-receipt.json"


def identity(directory: Path, context: str, node: str) -> dict:
    return {"directory": str(directory), "context": context, "node": node}


def read_receipt(directory: Path, expected: dict) -> bool:
    raw = existing(receipt_at(directory))
    if raw is None:
        return False
    try:
        record = json.loads(raw)
    except ValueError as error:
        raise AccessError("Invalid access ownership receipt; preserve and inspect it privately.") from error
    if record != expected:
        raise AccessError("Access ownership receipt does not match this deployment; no credentials changed.")
    return True


def check_node(kubeconfig: Path, context: str, node: str) -> None:
    try:
        result = subprocess.run(  # noqa: S603 -- fixed arguments; credentials reside only in the protected kubeconfig
            [
                executable("kubectl"),
                "--kubeconfig",
                str(kubeconfig),
                "--context",
                context,
                "--request-timeout=10s",
                "get",
                "node",
                node,
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
        response = json.loads(result.stdout) if result.returncode == 0 else None
        node_status = response.get("status") if isinstance(response, dict) else None
        conditions = node_status.get("conditions", []) if isinstance(node_status, dict) else []
        ready = isinstance(conditions, list) and any(
            isinstance(item, dict) and item.get("type") == "Ready" and item.get("status") == "True" for item in conditions
        )
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        raise AccessError("Controller cannot verify the K3s node with the selected DNS/IP, TLS and credentials.") from error
    if not ready:
        raise AccessError("Controller cannot verify the K3s node with the selected DNS/IP, TLS and credentials.")


def install(source: bytes, directory: Path, context: str, host: str, node: str, home: Path) -> bool:  # noqa: PLR0913, PLR0917 -- separate credential, owner and controller paths
    kube = kube_dir_for(home)
    owner = identity(directory, context, node)
    owned = read_receipt(directory, owner)
    target = kube / "config"
    dedicated = kube / f"{context}.yaml"
    current_raw = existing(target)
    dedicated_raw = existing(dedicated)
    if dedicated_raw is not None and not owned:
        raise AccessError("An unowned dedicated kubeconfig already exists; choose a different context.")
    current = (
        parse(current_raw)
        if current_raw is not None
        else {"apiVersion": "v1", "kind": "Config", "preferences": {}, "clusters": [], "users": [], "contexts": []}
    )
    for key in ("clusters", "users", "contexts"):
        names = [entry["name"] for entry in current[key]]
        if len(names) != len(set(names)):
            raise AccessError("Existing kubeconfig has duplicate entry names; correct it privately.")
        if context in names and not owned:
            raise AccessError("An unowned kubeconfig entry has the selected name; choose a different context.")
    if owned:
        previous = parse(dedicated_raw) if dedicated_raw is not None else None
        for key in ("clusters", "users", "contexts"):
            matching = [entry for entry in current[key] if entry["name"] == context]
            if matching and (previous is None or len(previous[key]) != 1 or previous[key][0] != matching[0]):
                raise AccessError("Deployment-owned context was changed outside bootstrap; preserve it and resolve the conflict privately.")
    prepared = renamed(source, context, host)
    prepared_raw = yaml.safe_dump(prepared, sort_keys=False).encode()

    # TLS, credentials and node readiness are checked before any durable client writes.
    fd, temporary = tempfile.mkstemp(prefix=".k3s-check-", dir=kube)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(prepared_raw)
        check_node(Path(temporary), context, node)
    finally:
        Path(temporary).unlink(missing_ok=True)

    for key in ("clusters", "users", "contexts"):
        current[key] = [entry for entry in current[key] if entry["name"] != context] + prepared[key]
    # Switching clusters is an explicit kubectl config use-context operation by the user.
    if not current.get("current-context"):
        current["current-context"] = context
    merged_raw = yaml.safe_dump(current, sort_keys=False).encode()
    if current_raw == merged_raw and dedicated_raw == prepared_raw:
        return False
    if not owned:
        write_private(receipt_at(directory), json.dumps(owner) + "\n")
    if current_raw is not None and current_raw != merged_raw:
        write_private(directory / f"k3s-access-backup-{uuid.uuid4().hex}.yaml", current_raw.decode())
    if dedicated_raw != prepared_raw:
        write_private(dedicated, prepared_raw.decode())
    if current_raw != merged_raw:
        write_private(target, merged_raw.decode())
    return True


def verify(directory: Path, context: str, node: str, home: Path) -> None:
    if not read_receipt(directory, identity(directory, context, node)):
        raise AccessError("No deployment-owned K3s context has been installed on this controller.")
    dedicated = home / ".kube" / f"{context}.yaml"
    raw = existing(dedicated)
    if raw is None or not isinstance(parse(raw), dict):
        raise AccessError("Deployment-owned kubeconfig is missing.")
    check_node(dedicated, context, node)
    merged = home / ".kube" / "config"
    main_raw = existing(merged)
    if main_raw is None:
        raise AccessError("Merged kubeconfig is missing.")
    source = parse(raw)
    main = parse(main_raw)
    for key in ("clusters", "users", "contexts"):
        if [entry for entry in main[key] if entry["name"] == context] != source[key]:
            raise AccessError("Merged K3s context differs from the deployment-owned copy.")
    check_node(merged, context, node)


def remove(directory: Path, context: str, node: str, home: Path) -> bool:
    """Remove only receipt-owned credentials; never contact the deleted cluster."""
    if not read_receipt(directory, identity(directory, context, node)):
        return False
    kube = home / ".kube"
    if not kube.exists():
        return False
    if kube.is_symlink() or not kube.is_dir() or stat.S_IMODE(kube.stat().st_mode) & 0o077:
        raise AccessError("Local kubeconfig directory has unsafe permissions or identity.")
    dedicated = kube / f"{context}.yaml"
    source_raw = existing(dedicated)
    merged_path = kube / "config"
    merged_raw = existing(merged_path)
    if source_raw is None and merged_raw is None:
        return False
    merged = parse(merged_raw) if merged_raw is not None else None
    if (
        source_raw is None
        and merged is not None
        and not any(entry["name"] == context for key in ("clusters", "users", "contexts") for entry in merged[key])
    ):
        return False
    if merged is not None:
        if source_raw is None and any(entry["name"] == context for key in ("clusters", "users", "contexts") for entry in merged[key]):
            raise AccessError("Owned credentials changed; dedicated kubeconfig is missing.")
        if source_raw is not None:
            source = parse(source_raw)
            for key in ("clusters", "users", "contexts"):
                if [entry for entry in merged[key] if entry["name"] == context] not in ([], source[key]):
                    raise AccessError("Owned kubeconfig differs from its dedicated copy; preserve operator edits.")
            if any(not isinstance(entry.get("context"), dict) for entry in merged["contexts"]):
                raise AccessError("Existing kubeconfig has an invalid context; preserve operator edits.")
            if any(
                entry["context"].get("cluster") == context or entry["context"].get("user") == context
                for entry in merged["contexts"]
                if entry["name"] != context
            ):
                raise AccessError("Another context references owned credentials; preserve it.")
            for key in ("clusters", "users", "contexts"):
                merged[key] = [entry for entry in merged[key] if entry["name"] != context]
            if merged.get("current-context") == context:
                merged.pop("current-context")
            updated = yaml.safe_dump(merged, sort_keys=False).encode()
            if updated != merged_raw:
                write_private(directory / f"k3s-access-backup-{uuid.uuid4().hex}.yaml", merged_raw.decode())
                write_private(merged_path, updated.decode())
    if source_raw is not None:
        dedicated.unlink()
    return True


def checked_context(context: str) -> None:
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", context):
        raise AccessError("Invalid context name.")


def admin_source() -> bytes:
    source = sys.stdin.buffer.read(1024 * 1024 + 1)
    if len(source) > 1024 * 1024:
        raise AccessError("Admin kubeconfig exceeds the supported size.")
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "verify"])
    parser.add_argument("directory")
    parser.add_argument("context")
    parser.add_argument("host")
    parser.add_argument("node")
    args = parser.parse_args()
    try:
        checked_context(args.context)
        directory = selected_directory(args.directory)
        if args.action == "install":
            # Read at most 1 MiB; no admin credentials appear in process arguments.
            source = admin_source()
            print("updated" if install(source, directory, args.context, args.host, args.node, Path.home()) else "unchanged")
        else:
            verify(directory, args.context, args.node, Path.home())
            print("ready")
    except (AccessError, ConfigError, OSError, UnicodeError, ValueError, KeyError, TypeError, yaml.YAMLError):
        print(
            "K3s access failed. Check the configured endpoint, TLS, controller permissions and context ownership; no credentials are displayed.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
