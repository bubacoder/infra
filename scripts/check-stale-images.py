#!/usr/bin/env python3

"""Script to report container image tags in Docker Compose files, ordered by how long ago
they were last changed in git history (oldest first), to help spot stale/un-updated images."""

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from utils.compose_processor import ComposeFileProcessor
from utils.docker_scanner import DockerComposeScanner
from utils.git_utils import get_git_root, get_line_last_changed


@dataclass
class ImageEntry:
    """A single image reference found in a compose file."""

    category: str
    stack: str
    service: str
    image: str
    file_path: str
    last_changed: datetime | None

    @property
    def label(self) -> str:
        """Human readable identifier: category/stack, with the compose service name appended
        if it differs from the stack name (e.g. a sidecar/init container)."""
        base = f"{self.category}/{self.stack}"
        return base if self.service == self.stack else f"{base} ({self.service})"


def configure_logger() -> logging.Logger:
    """Configure and return a logger for warnings encountered while scanning compose files.

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(__name__)

    handler = logging.StreamHandler()
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("  %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)

    return logger


def collect_image_entries(
    repository_path: Path,
    docker_path: str,
    logger: logging.Logger,
) -> list[ImageEntry]:
    """Scan all compose files and collect their image references with last-changed dates.

    Args:
        repository_path: Path to the repository root
        docker_path: Relative path to docker directory from repository root
        logger: Logger instance for logging messages

    Returns:
        List of ImageEntry, one per service that declares an image
    """
    scanner = DockerComposeScanner(repository_path, logger)
    compose_processor = ComposeFileProcessor(logger)

    docker_dir = repository_path / docker_path
    entries = []

    for service in scanner.scan_docker_directory(docker_path):
        compose_file = docker_dir / service["file_path"]
        repo_relative_path = f"{docker_path}/{service['file_path']}"
        stack_name = Path(service["file_path"]).parent.name

        for reference in compose_processor.extract_image_references(compose_file):
            last_changed = get_line_last_changed(repository_path, repo_relative_path, reference["line"])
            entries.append(
                ImageEntry(
                    category=service["category"] or "root",
                    stack=stack_name,
                    service=reference["service"],
                    image=reference["image"],
                    file_path=repo_relative_path,
                    last_changed=last_changed,
                )
            )

    return entries


def get_age_days(last_changed: datetime | None) -> int:
    """Age in days; uncommitted (None) entries are treated as brand new (age 0)."""
    if last_changed is None:
        return 0
    return (datetime.now(tz=UTC) - last_changed).days


def format_age(last_changed: datetime | None) -> str:
    """Format the age of a last-changed date as a human readable string.

    Args:
        last_changed: The last-changed datetime, or None if uncommitted

    Returns:
        Human readable age string (e.g. "412d ago", "uncommitted")
    """
    if last_changed is None:
        return "uncommitted"

    return f"{get_age_days(last_changed)}d ago"


def print_report(entries: list[ImageEntry], limit: int | None, min_age_days: int | None) -> None:
    """Print a human readable report of image entries, oldest first.

    Args:
        entries: List of image entries to report
        limit: Maximum number of rows to print, or None for no limit
        min_age_days: Only include entries at least this many days old, or None for no filter
    """
    # Uncommitted entries (last_changed is None) are treated as "just now" - newest, printed last
    entries = sorted(entries, key=lambda e: e.last_changed or datetime.now(tz=UTC))

    if min_age_days is not None:
        entries = [e for e in entries if get_age_days(e.last_changed) >= min_age_days]

    if limit is not None:
        entries = entries[:limit]

    print(f"{'LAST CHANGED':<12} {'AGE':<12} {'SERVICE':<45} {'IMAGE':<60}")
    print("-" * 129)

    for entry in entries:
        date_str = entry.last_changed.strftime("%Y-%m-%d") if entry.last_changed else "-"
        age_str = format_age(entry.last_changed)
        print(f"{date_str:<12} {age_str:<12} {entry.label:<45} {entry.image:<60}")


def main() -> None:
    """Parse arguments and print the stale image report."""
    parser = argparse.ArgumentParser(description="Report Docker Compose image tags ordered by git last-changed date (oldest first).")
    parser.add_argument("--repository-path", type=Path, help="Specify the path to the repository root")
    parser.add_argument("--docker-path", type=str, default="docker", help="Relative path to docker directory (default: docker)")
    parser.add_argument("--limit", type=int, help="Maximum number of rows to print (default: no limit)")
    parser.add_argument("--min-age-days", type=int, help="Only show images last changed at least this many days ago (hides recently updated images)")
    args = parser.parse_args()

    logger = configure_logger()

    try:
        repository_path = args.repository_path or Path(get_git_root())
        entries = collect_image_entries(repository_path, args.docker_path, logger)
        print_report(entries, args.limit, args.min_age_days)
    except Exception:
        logging.exception("Error generating stale image report")
        sys.exit(1)


if __name__ == "__main__":
    main()
