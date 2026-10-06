#!/usr/bin/env python3
"""Stream database exports to private host directories for Kopia snapshots."""

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backup import config, kopia, runner  # noqa: E402
from scripts.backup.common import DEFAULT_KOPIA_SOURCE, DEFAULT_KOPIA_VOLUMES_SOURCE, BackupError  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", nargs="?", help="Category/service (for example security/authentik)")
    parser.add_argument("--host", default="localhost", help="Host config directory (default: localhost symlink)")
    parser.add_argument("--keep-local", type=int, default=7, help="Completed local exports to retain per service (default: 7)")
    parser.add_argument("--kopia-source", default=DEFAULT_KOPIA_SOURCE, help="Scheduled Kopia B2 database-export source path")
    parser.add_argument("--kopia-volumes-source", default=DEFAULT_KOPIA_VOLUMES_SOURCE, help="Kopia source containing paired application files")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--dry-run", action="store_true", help="Check configuration and display the destination without exporting")
    action.add_argument("--verify-latest", action="store_true", help="Check the newest completed export's checksums and archive structure")
    action.add_argument("--run-all", action="store_true", help="Export all configured database services")
    action.add_argument("--prune-all", action="store_true", help="Prune old local exports only after a scheduled Kopia B2 snapshot")
    args = parser.parse_args()
    if bool(args.service) == bool(args.run_all or args.prune_all):
        parser.error("Choose one service or --run-all/--prune-all")
    try:
        volumes = config.docker_volumes(args.host)
        export_root = config.backup_root(args.host, volumes)
        if args.run_all or args.prune_all:
            failed = False
            for service in config.configured_services(args.host, export_root):
                try:
                    if args.prune_all:
                        removed = kopia.prune_local(
                            service,
                            volumes,
                            export_root,
                            args.keep_local,
                            sources=kopia.SnapshotSources(args.kopia_source, args.kopia_volumes_source),
                        )
                        print(f"{service}: B2 export and required paired snapshot coverage verified; removed {len(removed)} old local exports")
                    else:
                        target = config.load_target(service)
                        print(f"Completed export: {runner.perform_export(service, target, volumes, export_root, args.host)}")
                except (BackupError, OSError, BlockingIOError) as error:
                    print(f"{service}: {error}", file=sys.stderr)
                    failed = True
            if failed:
                sys.exit(1)
        else:
            target = config.load_target(args.service)
            if args.dry_run:
                if target["engine"] == "homeassistant":
                    source = "homeassistant:backup.create (requires host homeassistant/backup-token)"
                elif target["engine"] == "qdrant":
                    source = f"{target['container']}:full storage including collections and aliases"
                elif target["engine"] == "couchdb":
                    source = str(volumes / target["data"])
                elif target["engine"] == "mongodb":
                    source = f"{target['container']}:all databases; pause {target['writer']}"
                elif target.get("all_databases"):
                    source = f"{target['container']}:all non-template databases"
                elif target["engine"] == "postgresql":
                    source = f"{target['container']}:{target['database']}"
                else:
                    source = str(volumes / target["database"])
                print(f"{target['engine']} {source} -> {export_root}/{args.service.replace('/', '-')}")
            elif args.verify_latest:
                print(f"Verified export: {runner.verify_latest(args.service, target, volumes, export_root)}")
            else:
                print(f"Completed export: {runner.perform_export(args.service, target, volumes, export_root, args.host)}")
    except (BackupError, OSError, BlockingIOError) as error:
        print(f"Backup failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
