#!/usr/bin/env python3

"""Script to export all Docker Compose services metadata and documentation to YAML."""

import argparse
import logging
import math
import sys
from pathlib import Path

import yaml

from .docker_scanner import DockerComposeScanner
from .git_utils import get_git_root


def str_presenter(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


yaml.add_representer(str, str_presenter)


def export_services(repository_path, output_file, docker_path="docker", verbose=False):
    """Export all Docker Compose services to a YAML file.

    Args:
        repository_path: Path to the repository root
        output_file: Path to the output YAML file
        docker_path: Relative path to docker directory (default: "docker")
        verbose: Enable verbose logging
    """
    # Set up logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    if verbose:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('  %(levelname)s: %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.setLevel(logging.DEBUG)

    # Scan all services
    logger.info(f"Scanning Docker Compose files in {docker_path}")
    scanner = DockerComposeScanner(repository_path, logger)
    services = scanner.scan_docker_directory(docker_path)

    # Build output data structure
    output_data = {"services": []}

    for service in services:
        # Join head_lines into a single documentation string
        documentation = "".join(service["head_lines"]).strip()

        service_data = {
            "name": service["metadata"]["name"],
            "description": service["metadata"]["description"],
            "file_path": service["file_path"],
            "category": service["category"],
        }

        # Only include documentation if it's not empty
        if documentation:
            service_data["documentation"] = documentation

        output_data["services"].append(service_data)

    # Write to YAML file
    logger.info(f"Writing {len(services)} services to {output_file}")
    with open(output_file, "w") as f:
        yaml.dump(output_data, f, width=math.inf, default_flow_style=False, sort_keys=False, allow_unicode=True, Dumper=yaml.Dumper)

    logger.info("Export complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export Docker Compose services metadata and documentation to YAML."
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument(
        "--repository-path",
        type=str,
        help="Specify the path to the repository root"
    )
    parser.add_argument(
        "--output-file",
        type=str,
        help="Specify the output YAML file path"
    )
    parser.add_argument(
        "--docker-path",
        type=str,
        default="docker",
        help="Relative path to docker directory (default: docker)"
    )
    args = parser.parse_args()

    # Get repository path
    repository_path = Path(args.repository_path) if args.repository_path else Path(get_git_root())

    # Default output file if not specified
    output_file = Path(args.output_file) if args.output_file else repository_path / "services.yaml"

    # Export services
    try:
        export_services(repository_path, output_file, args.docker_path, args.verbose)
    except Exception:
        logging.exception("Error exporting services")
        sys.exit(1)
