#!/usr/bin/env python3
"""Manage only this project's three marked cron entries, preserving other jobs."""

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backup.common import DEFAULT_KOPIA_SOURCE, DEFAULT_KOPIA_VOLUMES_SOURCE, ROOT, BackupError  # noqa: E402
from scripts.backup.config import backup_root, docker_volumes  # noqa: E402

MARKERS = ("# managed:infra-db-backup-export", "# managed:infra-db-backup-prune", "# managed:infra-db-backup-snapshot")


@dataclass(frozen=True)
class Schedule:
    """Host-specific but non-secret backup timing and retention choices."""

    host: str
    export_time: str
    prune_time: str
    keep: int
    kopia_source: str
    kopia_volumes_source: str = DEFAULT_KOPIA_VOLUMES_SOURCE
    snapshot_time: str = "01:15"


def cron_time(value: str) -> tuple[int, int]:
    """Accept only a local HH:MM wall-clock time."""
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise BackupError("Times must use HH:MM in 24-hour host local time")
    hour, minute = value.split(":")
    return int(minute), int(hour)


def cron_entries(settings: Schedule, python: Path = Path(sys.executable), root: Path = ROOT) -> list[str]:
    """Build three entries using the interpreter running this tool."""
    if settings.keep < 1:
        raise BackupError("Keep at least one completed local export")
    if any(not source.startswith("/sources/") or ".." in Path(source).parts for source in (settings.kopia_source, settings.kopia_volumes_source)):
        raise BackupError("Invalid Kopia source path")
    log = shlex.quote(str(Path.home() / "infra-db-backup.log"))
    command = f"{shlex.quote(str(python))} {shlex.quote(str(root / 'scripts/backup/run.py'))}"
    prefix = "umask 077; "
    export = cron_time(settings.export_time)
    prune = cron_time(settings.prune_time)
    snapshot = cron_time(settings.snapshot_time)
    snapshot_command = f"{shlex.quote(str(python))} {shlex.quote(str(root / 'scripts/backup/latest.py'))}"
    return [
        f"{export[0]} {export[1]} * * * {prefix}{command} --host {shlex.quote(settings.host)} --run-all >> {log} 2>&1 {MARKERS[0]}",
        f"{prune[0]} {prune[1]} * * * {prefix}{command} --host {shlex.quote(settings.host)} --prune-all --keep-local {settings.keep} --kopia-source {shlex.quote(settings.kopia_source)} --kopia-volumes-source {shlex.quote(settings.kopia_volumes_source)} >> {log} 2>&1 {MARKERS[1]}",
        f"{snapshot[0]} {snapshot[1]} * * * {prefix}{snapshot_command} --host {shlex.quote(settings.host)} --kopia-source {shlex.quote(settings.kopia_source)} >> {log} 2>&1 {MARKERS[2]}",
    ]


def update_crontab(existing: str, entries: list[str]) -> str:
    """Replace only the marked database-backup jobs in a crontab."""
    lines = [line for line in existing.splitlines() if not any(line.rstrip().endswith(marker) for marker in MARKERS)]
    return "\n".join([*lines, *entries]) + "\n"


def installed_crontab() -> str:
    """Read the user's crontab, accepting only the expected absent state."""
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if result.returncode == 0:
        return result.stdout
    if result.returncode == 1 and "no crontab" in result.stderr.lower():
        return ""
    raise BackupError("Cannot read the current crontab")


def configure(args: argparse.Namespace) -> None:
    """Validate settings and apply them without modifying unrelated jobs."""
    if args.apply and os.geteuid() == 0:
        raise BackupError("Install the crontab as the non-root Docker host user")
    volumes = docker_volumes(args.host)
    exports = backup_root(args.host, volumes)
    if args.apply and exports.stat().st_uid != os.getuid():
        raise BackupError(f"Backup root belongs to another user: {exports}")
    if shutil.which("crontab") is None:
        raise BackupError("crontab executable not found")
    settings = Schedule(args.host, args.time, args.prune_time, args.keep_local, args.kopia_source, args.kopia_volumes_source, args.snapshot_time)
    entries = [] if args.remove else cron_entries(settings)
    if not args.apply:
        print("\n".join(entries))
        return
    current = installed_crontab()
    result = subprocess.run(["crontab", "-"], input=update_crontab(current, entries), text=True, capture_output=True, check=False)  # noqa: S603, S607
    if result.returncode != 0:
        raise BackupError(f"Cannot install database backup crontab: {result.stderr.strip()}")
    print("Removed marked database-backup jobs" if args.remove else "Installed/updated daily export, latest snapshot and retention jobs")


def main() -> None:
    """Preview by default; change crontab only when --apply is supplied."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost", help="Docker host config name (default: localhost)")
    parser.add_argument("--time", default="00:05", help="Daily export start, host local time (default: 00:05)")
    parser.add_argument("--prune-time", default="03:00", help="Daily retention check after Kopia (default: 03:00)")
    parser.add_argument("--snapshot-time", default="01:15", help="Daily latest-export snapshot, host local time (default: 01:15)")
    parser.add_argument("--keep-local", type=int, default=7, help="Completed exports to retain per service (default: 7)")
    parser.add_argument("--kopia-source", default=DEFAULT_KOPIA_SOURCE, help="Kopia B2 scheduled database-export source")
    parser.add_argument("--kopia-volumes-source", default=DEFAULT_KOPIA_VOLUMES_SOURCE, help="Kopia source containing paired application files")
    parser.add_argument("--apply", action="store_true", help="Install/update the three marked cron entries")
    parser.add_argument("--remove", action="store_true", help="Remove the three marked cron entries (requires --apply)")
    args = parser.parse_args()
    if args.remove and not args.apply:
        parser.error("--remove requires --apply")
    try:
        configure(args)
    except (BackupError, OSError) as error:
        print(f"Schedule failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
