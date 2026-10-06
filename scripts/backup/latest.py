"""Freeze checked latest exports as hard links and snapshot them under one lock."""

import argparse
import fcntl
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backup import config, runner  # noqa: E402
from scripts.backup.common import DEFAULT_KOPIA_SOURCE, BackupError, private_directory  # noqa: E402
from scripts.backup.kopia_policy import container_command  # noqa: E402

SERVICE_ERRORS = (BackupError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError)


@dataclass(frozen=True)
class PreparedView:
    path: Path
    included: int
    failures: tuple[str, ...] = ()


def link_export(export: Path, destination: Path) -> None:
    """Link only declared regular artifacts; never follow links outside an export."""
    manifest = json.loads((export / "manifest.json").read_text())
    private_directory(destination)
    for relative in ["manifest.json", *(entry["file"] for entry in manifest["files"])]:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or path == Path("."):
            raise BackupError(f"Invalid export artifact path: {relative}")
        source_parent, destination_parent = export, destination
        for part in path.parts[:-1]:
            source_parent /= part
            parent_info = source_parent.lstat()
            if not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid != os.getuid():
                raise BackupError(f"Unexpected export artifact directory: {source_parent}")
            destination_parent /= part
            private_directory(destination_parent)
        source = export / path
        info = source.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise BackupError(f"Export artifact must be a private owned regular file: {source}")
        os.link(source, destination / path, follow_symlinks=False)


def stage_candidate(service: str, target: dict, volumes: Path, export: Path, destination: Path) -> bool:
    """Revalidate a candidate before linking it; stale data is useful but degraded."""
    private_directory(export)
    runner.verify_export(service, target, volumes, export)
    manifest = json.loads((export / "manifest.json").read_text())
    created_at = datetime.fromisoformat(manifest["created_at"])
    now = datetime.now(UTC)
    if created_at.tzinfo is None or created_at > now:
        raise BackupError("Invalid publication time")
    private_directory(destination)
    link_export(export, destination / export.name)
    return created_at >= now - timedelta(days=1)


def select_service(service: str, volumes: Path, export_root: Path, staging: Path, view: Path) -> tuple[Path | None, list[str]]:
    """Isolate local failure and fall back to the previous frozen export if needed."""
    name = service.replace("/", "-")
    service_dir, destination = export_root / name, staging / name
    failures = []
    try:
        target = config.load_target(service)
    except SERVICE_ERRORS as error:
        return None, [f"{service}: invalid configuration: {error}"]

    def select(candidates: list[Path]) -> Path | None:
        for export in reversed(candidates):
            try:
                fresh = stage_candidate(service, target, volumes, export, destination)
            except SERVICE_ERRORS as error:
                failures.append(f"{service}: cannot use {export.name}: {error}")
                if destination.exists():
                    shutil.rmtree(destination)
            else:
                if not fresh:
                    failures.append(f"{service}: using stale verified export {export.name} (older than 24 hours)")
                print(f"{service}: selected {export.name}", flush=True)
                return export
        return None

    try:
        private_directory(service_dir)
        with (service_dir / ".lock").open("a+b") as lock:
            (service_dir / ".lock").chmod(0o600)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            candidates = runner.completed_exports(service_dir)
            if not candidates:
                raise BackupError("No completed exports")
            selected = select(candidates)
            if selected is not None:
                return selected, failures
    except SERVICE_ERRORS as error:
        failures.append(f"{service}: local export selection failed: {error}")

    previous = view / name
    if previous.exists():
        try:
            private_directory(previous)
            selected = select(runner.completed_exports(previous))
            if selected is not None:
                return selected, failures
        except SERVICE_ERRORS as error:
            failures.append(f"{service}: previous view unavailable: {error}")
    failures.append(f"{service}: omitted; no usable verified export")
    if destination.exists():
        shutil.rmtree(destination)
    return None, failures


def prepare_view(host: str, volumes: Path, export_root: Path) -> PreparedView:
    """Build completely before replacing contents of the stable bind-mount root.

    The caller holds .latest.lock throughout preparation and the subsequent snapshot.
    Service locks pin exports against concurrent publication and retention.
    """
    view = export_root / "latest"
    private_directory(view)
    for abandoned in export_root.glob(".latest-incomplete-*"):
        private_directory(abandoned)
        shutil.rmtree(abandoned)
    staging = Path(tempfile.mkdtemp(prefix=".latest-incomplete-", dir=export_root))
    try:
        included, failures = 0, []
        for service in sorted(config.configured_services(host, export_root)):
            selected, service_failures = select_service(service, volumes, export_root, staging, view)
            included += selected is not None
            failures.extend(service_failures)
            for failure in service_failures:
                print(f"DEGRADED: {failure}", file=sys.stderr, flush=True)
        if not included:
            raise BackupError("No usable verified exports for any service; preserving the previous view")
        # Never rename the bind-mounted root itself. Global installation failures
        # must prevent uploading a partially installed view.
        for child in view.iterdir():
            private_directory(child)
            shutil.rmtree(child)
        for child in staging.iterdir():
            child.rename(view / child.name)
        return PreparedView(view, included, tuple(failures))
    finally:
        shutil.rmtree(staging)


def check_mount(prefix: list[str], view: Path, source: str) -> None:
    """Refuse the old whole-history mount or a writable/missing latest mount."""
    result = subprocess.run(  # noqa: S603
        [prefix[0], "inspect", "--format={{json .Mounts}}", prefix[2]], capture_output=True, text=True, check=True, timeout=30
    )
    mounts = json.loads(result.stdout)
    if not any(
        mount.get("Type") == "bind"
        and mount.get("Destination") == source
        and Path(mount.get("Source", "")).resolve() == view.resolve()
        and mount.get("RW") is False
        for mount in mounts
    ):
        raise BackupError(f"Kopia must mount {view} read-only at {source}; recreate its container before snapshotting")


def snapshot_latest(host: str, *, source: str = DEFAULT_KOPIA_SOURCE, prepare_only: bool = False) -> PreparedView:
    volumes = config.docker_volumes(host)
    export_root = config.backup_root(host, volumes)
    private_directory(export_root)
    with (export_root / ".latest.lock").open("a+b") as lock:
        (export_root / ".latest.lock").chmod(0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prefix = None
        if not prepare_only:
            prefix = container_command("kopia-b2", source)
            check_mount(prefix, export_root / "latest", source)
        view = prepare_view(host, volumes, export_root)
        if prefix is not None:
            # No timeout: keep the view locked until the foreground upload exits.
            subprocess.run([*prefix, "snapshot", "create", source], check=True)  # noqa: S603
        return view


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost", help="Docker host configuration")
    parser.add_argument("--kopia-source", default=DEFAULT_KOPIA_SOURCE)
    parser.add_argument("--prepare-only", action="store_true", help="Populate the view for migration without creating a snapshot")
    args = parser.parse_args()
    try:
        result = snapshot_latest(args.host, source=args.kopia_source, prepare_only=args.prepare_only)
        action = "prepared" if args.prepare_only else "snapshotted"
        print(f"Latest export view {action}: {result.path}; {result.included} services included", flush=True)
        if result.failures:
            print(f"DEGRADED: {len(result.failures)} service issue(s); available exports were {action}", file=sys.stderr)
            sys.exit(1)
    except (BackupError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Latest export snapshot failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
