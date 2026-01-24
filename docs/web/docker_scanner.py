"""Module for scanning Docker directories and collecting compose file data."""

import logging
import os
from pathlib import Path

from compose_processor import ComposeFileProcessor


class DockerComposeScanner:
    """Class for scanning Docker directories and collecting compose file data."""

    def __init__(self, repository_path: str | Path, logger: logging.Logger | None = None) -> None:
        """Initialize the DockerComposeScanner.

        Args:
            repository_path: Path to the repository root
            logger: Logger instance for logging messages. If None, creates a new logger.
        """
        self.repository_path = Path(repository_path)
        self.logger = logger or logging.getLogger(__name__)
        self.compose_processor = ComposeFileProcessor(self.logger)

    def scan_docker_directory(self, docker_path: str = "docker") -> list[dict]:
        """Scan docker directory and collect data from all compose files.

        Scans for category directories (containing README.md) and looks for
        service compose files in subdirectories following the pattern:
        <category>/<service>/<service>.yaml

        Args:
            docker_path: Relative path to docker directory from repository root

        Returns:
            List of dictionaries, each containing:
                - file_path: Path to compose file relative to docker directory
                - category: Category path (e.g., "security", "media/video")
                - metadata: dict with name, description, icon, icon_url
                - head_lines: list of comment lines before "---"
                - yaml_lines: list of YAML content lines after "---"
                - has_readme: bool indicating if category contains README.md
        """
        source_dir = self.repository_path / docker_path
        services = []

        for root, dirs, files in os.walk(source_dir):
            has_readme = "README.md" in files
            if not has_readme:
                continue

            root_path = Path(root)
            category_path = root_path.relative_to(source_dir)
            category = str(category_path) if category_path != Path(".") else ""

            for service_dir_name in dirs:
                if service_dir_name == "config":
                    continue

                compose_file = self._find_compose_file(root_path / service_dir_name, service_dir_name)
                if not compose_file:
                    continue

                data = self.compose_processor.extract_compose_file_data(compose_file)
                if not data:
                    continue

                services.append(
                    {
                        "file_path": str(compose_file.relative_to(source_dir)),
                        "category": category,
                        "metadata": data["metadata"],
                        "head_lines": data["head_lines"],
                        "yaml_lines": data["yaml_lines"],
                        "has_readme": has_readme,
                    }
                )

        return services

    def _find_compose_file(self, service_dir: Path, service_name: str) -> Path | None:
        """Find compose file for a service, checking both .yaml and .yml extensions.

        Args:
            service_dir: Directory containing the service
            service_name: Name of the service

        Returns:
            Path to compose file if found, None otherwise
        """
        for extension in ("yaml", "yml"):
            compose_file = service_dir / f"{service_name}.{extension}"
            if compose_file.exists():
                return compose_file
        return None

    def get_services_by_category(self, docker_path: str = "docker") -> dict[str, list[dict]]:
        """Scan docker directory and organize services by category.

        Args:
            docker_path: Relative path to docker directory from repository root

        Returns:
            Dictionary mapping category names to lists of service data
        """
        services = self.scan_docker_directory(docker_path)
        by_category: dict[str, list[dict]] = {}

        for service in services:
            category = service["category"] or "root"
            by_category.setdefault(category, []).append(service)

        return by_category
