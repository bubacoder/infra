"""Module for scanning Docker directories and collecting compose file data."""

import logging
import os
from pathlib import Path

from compose_processor import ComposeFileProcessor


class DockerComposeScanner:
    """Class for scanning Docker directories and collecting compose file data."""

    def __init__(self, repository_path, logger=None):
        """Initialize the DockerComposeScanner.

        Args:
            repository_path: Path to the repository root
            logger: Logger instance for logging messages. If None, creates a new logger.
        """
        self.repository_path = Path(repository_path)
        self.logger = logger or logging.getLogger(__name__)
        self.compose_processor = ComposeFileProcessor(self.logger)

    def scan_docker_directory(self, docker_path="docker"):
        """Scan docker directory and collect data from all compose files.

        Only processes compose files in directories that contain a README.md file.
        This prevents processing configuration yaml files in subdirectories.

        Args:
            docker_path: Relative path to docker directory from repository root

        Returns:
            list: List of dictionaries, each containing:
                - file_path: Path to compose file relative to docker directory
                - category: Category path (e.g., "security", "media/video")
                - metadata: dict with name, description, icon, icon_url
                - head_lines: list of comment lines before "---"
                - yaml_lines: list of YAML content lines after "---"
                - has_readme: bool indicating if directory contains README.md
        """
        source_dir = self.repository_path / docker_path
        services = []

        # Walk through the source directory recursively
        for root, _, files in os.walk(source_dir):
            root_path = Path(root)
            has_readme = "README.md" in files

            # Only process compose files in directories that contain README.md
            if not has_readme:
                continue

            # Process all compose files in this directory
            for file in files:
                if file.endswith((".yaml", ".yml")):
                    source_file_path = root_path / file
                    relative_path = source_file_path.relative_to(source_dir)

                    # Extract category from path (e.g., "security" or "media/video")
                    category = str(relative_path.parent) if relative_path.parent != Path(".") else ""

                    # Extract all data from the compose file
                    data = self.compose_processor.extract_compose_file_data(source_file_path)

                    if data:
                        services.append({
                            "file_path": str(relative_path),
                            "category": category,
                            "metadata": data["metadata"],
                            "head_lines": data["head_lines"],
                            "yaml_lines": data["yaml_lines"],
                            "has_readme": has_readme,
                        })

        return services

    def get_services_by_category(self, docker_path="docker"):
        """Scan docker directory and organize services by category.

        Args:
            docker_path: Relative path to docker directory from repository root

        Returns:
            dict: Dictionary mapping category names to lists of service data
        """
        services = self.scan_docker_directory(docker_path)
        by_category = {}

        for service in services:
            category = service["category"] or "root"
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(service)

        return by_category
