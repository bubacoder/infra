"""Preview/apply repository-managed Kopia source schedules, retention and ignores."""

import argparse
import copy
import json
import re
import sys
from pathlib import Path

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backup.common import DEFAULT_KOPIA_VOLUMES_SOURCE, ROOT, BackupError  # noqa: E402
from scripts.backup.kopia_policy import collect_ignores, container_command, kopia_command  # noqa: E402

SETTINGS = ROOT / "docker/backup/kopia-b2/snapshots.yaml"
RETENTION = {name: "keep" + name.title() for name in ("latest", "hourly", "daily", "weekly", "monthly", "annual")}


def load_settings(path: Path) -> list[dict]:
    try:
        document = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as error:
        raise BackupError(f"Cannot load Kopia snapshot settings: {error}") from error
    if not isinstance(document, dict) or set(document) != {"version", "policies"} or document["version"] != 1:
        raise BackupError("Invalid Kopia snapshot settings")
    policies = document["policies"]
    if not isinstance(policies, list) or not policies:
        raise BackupError("Expected a nonempty policy list")
    sources = set()
    for item in policies:
        if not isinstance(item, dict) or set(item) - {"source", "time", "manual", "retention", "ignore", "application_ignores"}:
            raise BackupError("Invalid Kopia source definition")
        source = item.get("source")
        if not isinstance(source, str) or not source.startswith("/sources/") or ".." in Path(source).parts or source in sources:
            raise BackupError("Invalid or duplicate Kopia source")
        sources.add(source)
        if item.get("manual") is True:
            if "time" in item:
                raise BackupError("Manual sources cannot declare a snapshot time")
            if set(item) == {"source", "manual"}:
                continue
        elif "manual" in item or not isinstance(item.get("time"), str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", item["time"]):
            raise BackupError("Expected an HH:MM snapshot time")
        retention = item.get("retention")
        if (
            not isinstance(retention, dict)
            or set(retention) != set(RETENTION)
            or any(type(value) is not int or value < 0 for value in retention.values())
        ):
            raise BackupError("Expected all six nonnegative retention limits")
        if retention["latest"] < 1:
            raise BackupError("Snapshot retention must keep at least one latest snapshot")
        if "application_ignores" in item:
            if item["application_ignores"] is not True or source != DEFAULT_KOPIA_VOLUMES_SOURCE or "ignore" in item:
                raise BackupError("Application ignores belong only to the Docker-volumes source")
        elif not isinstance(item.get("ignore"), list) or any(
            not isinstance(pattern, str) or not pattern.strip() or any(char in pattern for char in "\n\r\x00") for pattern in item["ignore"]
        ):
            raise BackupError("Expected an explicit source ignore list")
    return policies


def defined_policy(prefix: list[str], target: str) -> dict | None:
    try:
        policies = json.loads(kopia_command(prefix, "policy", "list", "--json"))
    except ValueError as error:
        raise BackupError("Invalid Kopia policy listing") from error
    if not isinstance(policies, list):
        raise BackupError("Unexpected Kopia policy listing")
    matches = [p for p in policies if f"{p['target']['userName']}@{p['target']['host']}:{p['target']['path']}" == target]
    if len(matches) > 1:
        raise BackupError(f"Multiple policies found for {target}")
    return matches[0] if matches else None


def desired_fields(item: dict) -> dict:
    if item.get("manual") and "retention" not in item:
        return {"scheduling": {"manual": True}}
    scheduling = {"manual": True}
    if not item.get("manual"):
        hour, minute = map(int, item["time"].split(":"))
        scheduling = {"timeOfDay": [{"hour": hour, "min": minute}], "manual": False, "runMissed": True}
    ignores = collect_ignores() if item.get("application_ignores") else item["ignore"]
    return {
        "scheduling": scheduling,
        "retention": {RETENTION[name]: value for name, value in item["retention"].items()},
        "files": {"ignore": list(dict.fromkeys(ignores))},
    }


def matches_fields(policy: dict, desired: dict) -> bool:
    scheduling = policy.get("scheduling", {})
    expected = desired["scheduling"]
    if bool(scheduling.get("manual")) != expected["manual"] or scheduling.get("timeOfDay", []) != expected.get("timeOfDay", []):
        return False
    if "retention" not in desired:
        return not scheduling.get("intervalSeconds") and not scheduling.get("cron")
    return (
        (expected["manual"] or scheduling.get("runMissed") is True)
        and not scheduling.get("intervalSeconds")
        and not scheduling.get("cron")
        and all(policy.get("retention", {}).get(key) == value for key, value in desired["retention"].items())
        and set(policy.get("files", {}).get("ignore", [])) == set(desired["files"]["ignore"])
    )


def unmanaged_fields(policy: dict, desired: dict) -> dict:
    result = copy.deepcopy(policy)
    result.pop("id", None)
    for key in ("timeOfDay", "manual", "runMissed", "intervalSeconds", "cron"):
        result.get("scheduling", {}).pop(key, None)
    if "retention" in desired:
        for key in desired["retention"]:
            result.get("retention", {}).pop(key, None)
        result.get("files", {}).pop("ignore", None)
    return result


def sync_policy(prefix: list[str], target: str, item: dict, *, apply: bool = False) -> None:
    before = defined_policy(prefix, target)
    desired = desired_fields(item)
    if before and matches_fields(before, desired):
        print(f"{target}: policy already matches YAML")
        return
    print(f"{target}: {'manual-only' if item.get('manual') else 'daily ' + item['time']}; {'update' if before else 'create'}")
    if not apply:
        return
    # Kopia 0.23.1's --manual clears time/interval/cron but bypasses run-missed
    # handling, leaving a policy that its strict manual-mode validation rejects.
    if item.get("manual") and before and "runMissed" in before.get("scheduling", {}):
        kopia_command(prefix, "policy", "set", "--run-missed=inherit", target)
    # --manual already clears all schedules and cannot be combined with time flags.
    args = ["--manual"] if item.get("manual") else ["--no-manual", f"--snapshot-time={item['time']}", "--run-missed=true"]
    if not item.get("manual") and before and (before.get("scheduling", {}).get("intervalSeconds") or before.get("scheduling", {}).get("cron")):
        raise BackupError(f"Unexpected interval/cron schedule on {target}; inspect before replacing")
    if "retention" in desired:
        args.extend(f"--keep-{name}={value}" for name, value in item["retention"].items())
        current = (before or {}).get("files", {}).get("ignore", [])
        wanted = desired["files"]["ignore"]
        args.extend(f"--add-ignore={pattern}" for pattern in wanted if pattern not in current)
        args.extend(f"--remove-ignore={pattern}" for pattern in current if pattern not in wanted)
    kopia_command(prefix, "policy", "set", *args, target)
    after = defined_policy(prefix, target)
    if after is None or not matches_fields(after, desired):
        raise BackupError(f"Policy verification failed for {target}")
    if before and unmanaged_fields(before, desired) != unmanaged_fields(after, desired):
        raise BackupError(f"Unmanaged policy settings changed for {target}")
    print(f"{target}: applied and verified")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, default=SETTINGS)
    parser.add_argument("--container", default="kopia-b2")
    parser.add_argument("--policy-user", default="root")
    parser.add_argument("--policy-host", default="nest")
    parser.add_argument("--server-address", default="http://127.0.0.1:80", help="Kopia server address inside the container")
    parser.add_argument("--apply", action="store_true", help="Apply managed policy fields; preview by default")
    args = parser.parse_args()
    try:
        policies = load_settings(args.settings)
        prefix = container_command(args.container, DEFAULT_KOPIA_VOLUMES_SOURCE)
        for item in policies:
            sync_policy(prefix, f"{args.policy_user}@{args.policy_host}:{item['source']}", item, apply=args.apply)
        if args.apply:
            kopia_command(prefix, "server", "refresh", f"--address={args.server_address}")
            print("Refreshed the running Kopia server to load the source policies.")
        else:
            print("Preview only; use --apply to synchronize snapshot policies.")
    except (BackupError, OSError) as error:
        print(f"Kopia snapshot policy synchronization failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
