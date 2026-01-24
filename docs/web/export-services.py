#!/usr/bin/env python3

"""Script to export all Docker Compose services metadata and documentation to YAML."""

import argparse
import logging
import math
import sys
from pathlib import Path
from typing import Any

import yaml
from docker_scanner import DockerComposeScanner
from git_utils import get_git_root


def str_presenter(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    """Configure YAML string representation to use block style for multiline strings.

    Args:
        dumper: YAML dumper instance
        data: String data to represent

    Returns:
        YAML scalar node with appropriate style
    """
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, str_presenter)


def configure_logger(verbose: bool) -> logging.Logger:
    """Configure and return a logger with appropriate verbosity level.

    Args:
        verbose: Enable debug level logging

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(__name__)

    if not verbose:
        logger.setLevel(logging.INFO)
        return logger

    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("  %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    return logger


def build_service_data(service: dict[str, Any]) -> dict[str, Any]:
    """Build service data dictionary from scanned service information.

    Args:
        service: Service data from scanner

    Returns:
        Dictionary with service name, description, file path, category, and optional documentation
    """
    documentation = "\n".join(line.rstrip("\n") for line in service["head_lines"]).strip()

    service_data = {
        "name": service["metadata"]["name"],
        "description": service["metadata"]["description"],
        "file_path": service["file_path"],
        "category": service["category"],
    }

    if documentation:
        service_data["documentation"] = documentation

    return service_data


def write_yaml(data: dict[str, Any], output_stream: Any) -> None:
    """Write data to YAML with consistent formatting.

    Args:
        data: Data to write
        output_stream: File stream or stdout
    """
    yaml.dump(
        data,
        output_stream,
        width=math.inf,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        indent=2,
        Dumper=yaml.Dumper,
    )


def export_services(
    repository_path: Path,
    output_file: Path | None,
    docker_path: str = "docker",
    verbose: bool = False,
) -> None:
    """Export all Docker Compose services to a YAML file or stdout.

    Args:
        repository_path: Path to the repository root
        output_file: Path to the output YAML file, or None for stdout
        docker_path: Relative path to docker directory (default: "docker")
        verbose: Enable verbose logging
    """
    logger = configure_logger(verbose)

    logger.info(f"Scanning Docker Compose files in {docker_path}")
    scanner = DockerComposeScanner(repository_path, logger)
    services = scanner.scan_docker_directory(docker_path)

    output_data = {"services": [build_service_data(service) for service in services]}

    if output_file is None:
        logger.info("Writing services to stdout")
        write_yaml(output_data, sys.stdout)
    else:
        logger.info(f"Writing {len(services)} services to {output_file}")
        with open(output_file, "w", encoding="utf-8") as stream:
            write_yaml(output_data, stream)

    logger.info("Export complete")


def main() -> None:
    """Parse arguments and execute the export."""
    parser = argparse.ArgumentParser(description="Export Docker Compose services metadata and documentation to YAML.")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--repository-path",
        type=Path,
        help="Specify the path to the repository root",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help="Specify the output YAML file path (defaults to stdout if omitted)",
    )
    parser.add_argument(
        "--docker-path",
        type=str,
        default="docker",
        help="Relative path to docker directory (default: docker)",
    )
    args = parser.parse_args()

    repository_path = args.repository_path or Path(get_git_root())

    try:
        export_services(repository_path, args.output_file, args.docker_path, args.verbose)
    except Exception:
        logging.exception("Error exporting services")
        sys.exit(1)


if __name__ == "__main__":
    main()
