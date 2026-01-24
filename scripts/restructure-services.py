#!/usr/bin/env python3
"""
Docker service restructuring script.

This script reorganizes Docker Compose service directories by moving them into
dedicated subdirectories with a standardized structure.
"""

import argparse
import logging
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ServiceInfo:
    """Information about a Docker service."""

    name: str
    description: str
    file_path: str
    category: str
    documentation: str

    @property
    def category_path(self) -> str:
        """Extract category path from file_path (e.g., 'ai' or 'media/video')."""
        # file_path is like "ai/litellm.yaml" or "media/video/jellyfin.yaml"
        path_parts = self.file_path.split("/")
        # Everything except the last part (filename) is the category path
        return "/".join(path_parts[:-1])

    @property
    def service_name(self) -> str:
        """Extract service name from file_path (e.g., 'litellm')."""
        # file_path is like "ai/litellm.yaml"
        filename = self.file_path.split("/")[-1]
        # Remove .yaml extension
        return filename.rsplit(".", 1)[0]


@dataclass
class RestructureConfig:
    """Configuration for the restructure operation."""

    repo_path: Path
    dry_run: bool = True
    service_list_path: Path | None = None
    verbose: bool = False
    service_filter: str | None = None

    def __post_init__(self):
        """Validate and normalize paths."""
        self.repo_path = self.repo_path.resolve()
        if self.service_list_path is None:
            self.service_list_path = self.repo_path / "docs" / "service-list.yaml"
        else:
            self.service_list_path = self.service_list_path.resolve()


@dataclass
class ServicePaths:
    """Paths related to a service restructure operation."""

    docker_dir: Path
    compose_file: Path
    config_dir: Path
    stack_dir: Path
    category_dir: Path
    config_exists: bool


def load_service_list(path: Path) -> list[ServiceInfo]:
    """Load and parse the service list from YAML file.

    Args:
        path: Path to the service-list.yaml file

    Returns:
        list[ServiceInfo]: List of ServiceInfo objects

    Raises:
        SystemExit: If the file cannot be loaded or parsed
    """
    try:
        with open(path) as f:
            data = yaml.safe_load(f)

        if not data or "services" not in data:
            logger.error(f"Invalid service list format in {path}: 'services' key not found")
            sys.exit(1)

        services = []
        for service_data in data["services"]:
            try:
                services.append(
                    ServiceInfo(
                        name=service_data.get("name", ""),
                        description=service_data.get("description", ""),
                        file_path=service_data.get("file_path", ""),
                        category=service_data.get("category", ""),
                        documentation=service_data.get("documentation", ""),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping invalid service entry: {e}")

        return services  # noqa: TRY300

    except FileNotFoundError:
        logger.exception(f"Service list file not found: {path}")
        sys.exit(1)
    except yaml.YAMLError:
        logger.exception(f"Error parsing YAML file {path}")
        sys.exit(1)
    except Exception:
        logger.exception(f"Error loading service list from {path}")
        sys.exit(1)


def validate_service_paths(service: ServiceInfo, docker_dir: Path) -> tuple[bool, str]:
    """Validate that service paths exist and are accessible.

    Args:
        service: ServiceInfo object to validate
        docker_dir: Base docker directory path

    Returns:
        tuple[bool, str]: (is_valid, error_message)
                          Special case: (False, "already_restructured") if already in new format
    """
    category_dir = docker_dir / service.category_path
    new_location = category_dir / service.service_name / f"{service.service_name}.yaml"

    # Check if service is already restructured
    if new_location.exists() and new_location.is_file():
        return False, "already_restructured"

    # Check if compose file exists at old location
    compose_file = docker_dir / service.file_path
    if not compose_file.exists():
        return False, f"Compose file not found: {compose_file}"

    if not compose_file.is_file():
        return False, f"Compose path is not a file: {compose_file}"

    return True, ""


def transform_volume_mounts(compose_content: str, service_name: str) -> str:
    """Transform volume mount paths from ./<service>/ to ./config/.

    Transforms two patterns:
    - ./<service_name>/<path>:... → ./config/<path>:...
    - ./<service_name>:... → ./config:...

    Does not transform:
    - Absolute paths (starting with /)
    - Environment variables (${...})
    - System mounts

    Args:
        compose_content: Content of the compose file
        service_name: Name of the service (used to match volume paths)

    Returns:
        str: Transformed compose file content
    """
    # Pattern 1: Match "./<service_name>/<path>" and replace with "./config/<path>"
    pattern1 = rf"(\s+-\s+)\./{re.escape(service_name)}/(.+)"
    replacement1 = r"\1./config/\2"
    transformed = re.sub(pattern1, replacement1, compose_content, flags=re.MULTILINE)

    # Pattern 2: Match "./<service_name>:" (without trailing slash) and replace with "./config:"
    pattern2 = rf"(\s+-\s+)\./{re.escape(service_name)}(:)"
    replacement2 = r"\1./config\2"
    transformed = re.sub(pattern2, replacement2, transformed, flags=re.MULTILINE)

    return transformed


def _show_transform_preview(content: str, service_name: str, messages: list[str]) -> None:
    """Show preview of volume mount transformations that would be applied.

    Args:
        content: Compose file content
        service_name: Name of the service
        messages: List to append preview messages to
    """
    transformed = transform_volume_mounts(content, service_name)
    if transformed == content:
        return

    # Pattern 1: ./<service_name>/<path>
    pattern1 = rf"\./{re.escape(service_name)}/(.+?)(?=:|$)"
    matches1 = re.findall(pattern1, content)
    for match in matches1:
        messages.append(f"→ Would transform: ./{service_name}/{match} → ./config/{match}")

    # Pattern 2: ./<service_name>: (without trailing slash)
    pattern2 = rf"\./{re.escape(service_name)}:"
    if re.search(pattern2, content):
        messages.append(f"→ Would transform: ./{service_name}: → ./config:")


def _show_transform_results(original: str, transformed: str, service_name: str, messages: list[str]) -> None:
    """Show results of volume mount transformations that were applied.

    Args:
        original: Original compose file content
        transformed: Transformed compose file content
        service_name: Name of the service
        messages: List to append result messages to
    """
    if transformed == original:
        return

    # Pattern 1: ./<service_name>/<path>
    pattern1 = rf"\./{re.escape(service_name)}/(.+?)(?=:|$)"
    matches1 = re.findall(pattern1, original)
    for match in matches1:
        messages.append(f"✓ Transformed: ./{service_name}/{match} → ./config/{match}")

    # Pattern 2: ./<service_name>: (without trailing slash)
    pattern2 = rf"\./{re.escape(service_name)}:"
    if re.search(pattern2, original):
        messages.append(f"✓ Transformed: ./{service_name}: → ./config:")


def _perform_dry_run(
    service: ServiceInfo,
    paths: ServicePaths,
    final_dir: Path,
    messages: list[str],
) -> tuple[bool, str]:
    """Show what would be done during restructure without making changes.

    Args:
        service: ServiceInfo object
        paths: ServicePaths object with all path information
        final_dir: Path to final directory
        messages: List of messages to display

    Returns:
        tuple[bool, str]: (success, message)
    """
    messages.append(f"→ Would create: {paths.stack_dir.relative_to(paths.docker_dir)}/")
    messages.append(
        f"→ Would move: {paths.compose_file.relative_to(paths.docker_dir)} → {paths.stack_dir.relative_to(paths.docker_dir)}/{service.service_name}.yaml"
    )

    try:
        with open(paths.compose_file) as f:
            content = f.read()
        _show_transform_preview(content, service.service_name, messages)
    except Exception as e:
        messages.append(f"⚠ Could not read compose file for transform preview: {e}")

    if paths.config_exists:
        messages.append(
            f"→ Would move config: {paths.config_dir.relative_to(paths.docker_dir)}/ → {paths.stack_dir.relative_to(paths.docker_dir)}/config/"
        )

    messages.append(
        f"→ Would rename: {paths.stack_dir.relative_to(paths.docker_dir)}/ → {final_dir.relative_to(paths.docker_dir)}/"
    )

    return True, "\n  ".join(messages)


def _perform_restructure(
    service: ServiceInfo,
    paths: ServicePaths,
    messages: list[str],
) -> None:
    """Perform the actual restructuring operations.

    Args:
        service: ServiceInfo object
        paths: ServicePaths object with all path information
        messages: List to append operation messages to

    Raises:
        Exception: If any operation fails
    """
    # Create temporary directory for atomic operations
    with tempfile.TemporaryDirectory(dir=paths.category_dir) as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        temp_stack = temp_dir / f"{service.service_name}-stack"
        temp_stack.mkdir(parents=True, exist_ok=True)
        messages.append(f"✓ Created: {paths.stack_dir.relative_to(paths.docker_dir)}/")

        # Read and transform compose file
        with open(paths.compose_file) as f:
            content = f.read()
        transformed_content = transform_volume_mounts(content, service.service_name)

        # Write transformed compose file to stack directory
        new_compose_file = temp_stack / f"{service.service_name}.yaml"
        with open(new_compose_file, "w") as f:
            f.write(transformed_content)
        messages.append(f"✓ Created: {paths.stack_dir.relative_to(paths.docker_dir)}/{service.service_name}.yaml")

        _show_transform_results(content, transformed_content, service.service_name, messages)

        # Move config directory if it exists
        if paths.config_exists:
            temp_config = temp_stack / "config"
            shutil.copytree(paths.config_dir, temp_config, dirs_exist_ok=True)
            messages.append(
                f"✓ Moved config: {paths.config_dir.relative_to(paths.docker_dir)}/ → {paths.stack_dir.relative_to(paths.docker_dir)}/config/"
            )

        # Move temp directory to final location
        if paths.stack_dir.exists():
            shutil.rmtree(paths.stack_dir)
        shutil.move(str(temp_stack), str(paths.stack_dir))


def restructure_service(service: ServiceInfo, docker_dir: Path, dry_run: bool) -> tuple[bool, str]:
    """Restructure a single service to the new directory layout.

    Steps:
    1. Validate service paths
    2. Create <service>-stack/ directory
    3. Copy compose file to stack directory
    4. Read, transform, and write updated compose file
    5. If config directory exists, move contents to <service>-stack/config/
    6. Delete old config directory if it exists
    7. Rename <service>-stack/ to <service>/

    Args:
        service: ServiceInfo object
        docker_dir: Base docker directory path
        dry_run: If True, only show what would be done

    Returns:
        tuple[bool, str]: (success, message)
    """
    valid, error_msg = validate_service_paths(service, docker_dir)
    if not valid:
        if error_msg == "already_restructured":
            return False, "Already restructured (skipping)"
        return False, error_msg

    category_dir = docker_dir / service.category_path
    compose_file = docker_dir / service.file_path
    config_dir = category_dir / service.service_name
    stack_dir = category_dir / f"{service.service_name}-stack"
    final_dir = category_dir / service.service_name

    config_exists = config_dir.exists() and config_dir.is_dir()

    # Create ServicePaths object to group related paths
    paths = ServicePaths(
        docker_dir=docker_dir,
        compose_file=compose_file,
        config_dir=config_dir,
        stack_dir=stack_dir,
        category_dir=category_dir,
        config_exists=config_exists,
    )

    messages = [f"✓ Compose file exists: {compose_file.relative_to(docker_dir)}"]
    if config_exists:
        messages.append(f"✓ Config directory exists: {config_dir.relative_to(docker_dir)}/")
    else:
        messages.append("ℹ No config directory (OK)")

    if dry_run:
        return _perform_dry_run(service, paths, final_dir, messages)

    # Actually perform the restructuring
    try:
        _perform_restructure(service, paths, messages)

        # Delete old compose file
        compose_file.unlink()

        # Delete old config directory if it exists
        if config_exists:
            shutil.rmtree(config_dir)

        # Rename stack directory to final name
        if final_dir.exists():
            shutil.rmtree(final_dir)
        stack_dir.rename(final_dir)
        messages.append(f"✓ Renamed: {stack_dir.relative_to(docker_dir)}/ → {final_dir.relative_to(docker_dir)}/")

        return True, "\n  ".join(messages)

    except Exception:
        logger.exception(f"Error restructuring service {service.name}")
        return False, f"Error: {sys.exc_info()[1]}"


def _filter_services(services: list[ServiceInfo], service_filter: str | None) -> list[ServiceInfo]:
    """Filter services by name if a filter is provided.

    Args:
        services: List of all services
        service_filter: Service name to filter by (or None for all services)

    Returns:
        list[ServiceInfo]: Filtered list of services

    Raises:
        SystemExit: If filter provided but no matching service found
    """
    if not service_filter:
        return services

    filtered = [s for s in services if s.service_name == service_filter]
    if not filtered:
        logger.error(f"No service found matching: {service_filter}")
        sys.exit(1)

    return filtered


def _log_service_result(message: str, success: bool, verbose: bool) -> None:
    """Log the result of a service operation.

    Args:
        message: Result message
        success: Whether the operation succeeded
        verbose: Whether to show verbose output
    """
    if verbose or not success:
        for line in message.split("\n"):
            logger.info(f"  {line}")
    else:
        first_line = message.split("\n")[0]
        logger.info(f"  {first_line}")


def process_all_services(config: RestructureConfig) -> dict[str, tuple[bool, str]]:
    """Process all services from the service list.

    Args:
        config: RestructureConfig object

    Returns:
        dict: Map of service name to (success, message) tuple
    """
    services = load_service_list(config.service_list_path)
    services = _filter_services(services, config.service_filter)
    docker_dir = config.repo_path / "docker"

    mode_str = "DRY RUN (use --apply to make changes)" if config.dry_run else "APPLY MODE (making changes)"
    logger.info("=== Docker Service Restructure Tool ===")
    logger.info(f"Mode: {mode_str}")
    logger.info(f"Repository: {config.repo_path}")
    logger.info(f"Services to process: {len(services)}")
    logger.info("")

    results = {}
    for idx, service in enumerate(services, 1):
        service_path = f"{service.category_path}/{service.service_name}"
        logger.info(f"[{idx}/{len(services)}] Processing {service_path}")

        success, message = restructure_service(service, docker_dir, config.dry_run)
        results[service_path] = (success, message)

        _log_service_result(message, success, config.verbose)
        logger.info("")

    return results


def print_summary(results: dict[str, tuple[bool, str]]) -> None:
    """Print a summary of the restructure operation.

    Args:
        results: Map of service name to (success, message) tuple
    """
    total = len(results)
    successful = sum(1 for success, _ in results.values() if success)
    failed = total - successful

    logger.info("=== Summary ===")
    logger.info(f"Total: {total} | Successful: {successful} | Failed: {failed}")

    if failed == 0:
        return

    logger.info("")
    logger.info("Failed services:")
    for service_name, (success, message) in results.items():
        if not success:
            error_msg = message.split("\n")[-1] if "\n" in message else message
            logger.info(f"  - {service_name}: {error_msg}")


def _validate_paths(config: RestructureConfig) -> None:
    """Validate that required paths exist.

    Args:
        config: RestructureConfig object

    Raises:
        SystemExit: If paths are invalid
    """
    if not config.repo_path.exists():
        logger.error(f"Repository path does not exist: {config.repo_path}")
        sys.exit(1)

    if not config.service_list_path.exists():
        logger.error(f"Service list file not found: {config.service_list_path}")
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Restructure Docker service directories to standardized layout.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run (shows what would be done)
  %(prog)s /path/to/repo

  # Actually perform restructuring
  %(prog)s /path/to/repo --apply

  # Process single service for testing
  %(prog)s /path/to/repo --service litellm --apply

  # Verbose output
  %(prog)s /path/to/repo --apply --verbose
        """,
    )

    parser.add_argument("repo_path", type=Path, help="Path to the infrastructure repository")
    parser.add_argument("--apply", action="store_true", help="Actually perform the restructuring (default is dry-run)")
    parser.add_argument("--service-list", type=Path, help="Path to service list YAML (default: docs/service-list.yaml)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output (show all details)")
    parser.add_argument("--service", help="Process only specific service (for testing)")

    args = parser.parse_args()

    config = RestructureConfig(
        repo_path=args.repo_path,
        dry_run=not args.apply,
        service_list_path=args.service_list,
        verbose=args.verbose,
        service_filter=args.service,
    )

    _validate_paths(config)

    try:
        results = process_all_services(config)
        print_summary(results)

        failed = sum(1 for success, _ in results.values() if not success)
        if failed > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nInterrupted")
        sys.exit(130)


if __name__ == "__main__":
    main()
