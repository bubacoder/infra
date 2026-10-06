"""Combine manifest ignore rules and synchronize an existing Kopia source policy."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backup.common import DEFAULT_KOPIA_VOLUMES_SOURCE, ROOT, BackupError  # noqa: E402
from scripts.backup.config import load_definition  # noqa: E402


def collect_ignores(docker_dir: Path = ROOT / "docker") -> list[str]:
    """Preserve pattern spelling and ordering; remove duplicates across manifests."""
    paths = sorted(docker_dir.rglob("backup.yaml"))
    if not paths:
        raise BackupError(f"No backup manifests found under {docker_dir}")
    patterns = []
    for path in paths:
        target = load_definition(path)
        patterns.extend(target.get("files", {}).get("ignore", []))
    return list(dict.fromkeys(patterns))


def kopia_command(prefix: list[str], *args: str) -> str:
    try:
        result = subprocess.run([*prefix, *args], capture_output=True, text=True, check=True, timeout=120)  # noqa: S603
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise BackupError(f"Kopia command failed: {error}") from error
    return result.stdout


def read_policy(prefix: list[str], target: str) -> dict:
    """Use local (not inherited) ignores so parent rules remain independently managed."""
    try:
        policies = json.loads(kopia_command(prefix, "policy", "list", "--json"))
    except ValueError as error:
        raise BackupError("Invalid Kopia policy listing") from error
    if not isinstance(policies, list):
        raise BackupError("Unexpected Kopia policy listing")
    matches = []
    for policy in policies:
        source = policy.get("target", {})
        name = f"{source.get('userName')}@{source.get('host')}:{source.get('path')}"
        if name == target:
            matches.append(policy)
    if len(matches) != 1:
        raise BackupError(f"Expected exactly one existing Kopia policy for {target}; found {len(matches)}")
    return matches[0]


def synchronize(prefix: list[str], target: str, desired: list[str], *, apply: bool = False) -> bool:
    before = read_policy(prefix, target)
    current = before.get("files", {}).get("ignore", [])
    if not isinstance(current, list) or any(not isinstance(pattern, str) for pattern in current):
        raise BackupError("Unexpected Kopia ignore list")
    added = [pattern for pattern in desired if pattern not in current]
    removed = [pattern for pattern in current if pattern not in desired]
    print(f"Policy: {target}")
    print(f"Schedule: {json.dumps(before.get('scheduling', {}), sort_keys=True)}")
    print(f"Manifest ignores: {len(desired)}; add: {len(added)}; remove: {len(removed)}")
    for pattern in added:
        print(f"+ {pattern}")
    for pattern in removed:
        print(f"- {pattern}")
    if not added and not removed:
        print("Ignore rules already match the manifests.")
        return False
    if not apply:
        print("Preview only; use --apply to synchronize the ignore list.")
        return True
    # Kopia's clear flag skips additions, so apply the list delta in one update.
    kopia_command(
        prefix,
        "policy",
        "set",
        *(f"--add-ignore={pattern}" for pattern in added),
        *(f"--remove-ignore={pattern}" for pattern in removed),
        target,
    )
    after = read_policy(prefix, target)
    if set(after.get("files", {}).get("ignore", [])) != set(desired):
        raise BackupError("Kopia ignore list did not match the manifests after synchronization")
    for policy in (before, after):
        policy.pop("id", None)
        policy.get("files", {}).pop("ignore", None)
    if after != before:
        raise BackupError("Unexpected change to other Kopia policy settings; inspect the policy")
    print("Synchronized and verified; other policy settings are unchanged.")
    return True


def container_command(container: str, source: str) -> list[str]:
    if not source.startswith("/sources/") or ".." in Path(source).parts:
        raise BackupError("Invalid Kopia source path")
    docker = shutil.which("docker")
    if docker is None:
        raise BackupError("Docker executable not found")
    return [docker, "exec", container, "kopia", "--config-file=/app/config/repository.config"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="kopia-b2", help="Running Kopia container")
    parser.add_argument("--source", default=DEFAULT_KOPIA_VOLUMES_SOURCE, help="Whole-volume source path inside Kopia")
    parser.add_argument("--policy-user", default="root", help="Kopia source owner")
    parser.add_argument("--policy-host", default="nest", help="Kopia source host (not the host config directory)")
    parser.add_argument("--apply", action="store_true", help="Replace the source policy's explicit ignores with the YAML list")
    args = parser.parse_args()
    try:
        prefix = container_command(args.container, args.source)
        desired = collect_ignores()
        synchronize(prefix, f"{args.policy_user}@{args.policy_host}:{args.source}", desired, apply=args.apply)
    except (BackupError, OSError) as error:
        print(f"Kopia policy synchronization failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
