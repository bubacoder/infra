"""Module for processing Docker Compose files and extracting metadata."""

import logging
from pathlib import Path

import yaml


class ComposeFileProcessor:
    """Class for processing Docker Compose files and extracting metadata."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize the ComposeFileProcessor.

        Args:
            logger: Logger instance for logging messages. If None, creates a new logger.
        """
        self.logger = logger or logging.getLogger(__name__)

    def get_compose_metadata(self, file_path: Path) -> dict[str, str] | None:
        """Extract metadata from a docker-compose file.

        Args:
            file_path: Path to the docker-compose file

        Returns:
            Dictionary containing name, description, icon and icon URL from homepage labels.
            Returns None if the file is not a valid compose file (no services element).
        """
        try:
            compose_dict = self._load_compose_file(file_path)
            if not compose_dict:
                return None

            services = compose_dict.get("services", {})
            if not services or not isinstance(services, dict):
                return None

            homepage_labels = self._extract_homepage_labels(services)
            homepage_name = homepage_labels.get("name") or file_path.stem.capitalize()
            homepage_icon = homepage_labels.get("icon", "")

            icon_url = f"https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/{homepage_icon}" if homepage_icon else ""

            return {
                "name": homepage_name,
                "description": homepage_labels.get("description", ""),
                "icon": homepage_icon,
                "icon_url": icon_url,
            }
        except yaml.YAMLError:
            self.logger.exception(f"YAML parsing error in {file_path}")
            return None

    def _load_compose_file(self, file_path: Path) -> dict | None:
        """Load and validate a docker-compose file.

        Args:
            file_path: Path to the docker-compose file

        Returns:
            Dictionary representation of the compose file, or None if invalid
        """
        with open(file_path) as stream:
            compose_dict = yaml.safe_load(stream)

        if compose_dict is None:
            return None

        if not isinstance(compose_dict, dict):
            self.logger.warning(f"Skipping {file_path}: root element is not a dictionary")
            return None

        return compose_dict

    def _extract_homepage_labels(self, services: dict) -> dict[str, str]:
        """Extract homepage labels from Docker Compose services.

        Args:
            services: Dictionary of Docker Compose services

        Returns:
            Dictionary with homepage.name, homepage.description, and homepage.icon values
        """
        for service in services.values():
            labels = service.get("labels", {})

            # Normalize labels: convert list format to dict
            if isinstance(labels, list):
                labels_dict = {}
                for item in labels:
                    if isinstance(item, str) and "=" in item:
                        key, _, value = item.partition("=")
                        labels_dict[key] = value
                labels = labels_dict

            homepage_labels = {key.replace("homepage.", ""): value for key, value in labels.items() if key.startswith("homepage.")}

            if homepage_labels:
                return homepage_labels

        return {}

    def extract_compose_file_data(self, source_file_path: Path) -> dict[str, dict | list] | None:
        """Extract all information from a docker-compose file.

        Args:
            source_file_path: Path to the docker-compose file

        Returns:
            Dictionary with keys:
            - metadata: dict containing name, description, icon
            - head_lines: list of comment lines before "---"
            - yaml_lines: list of YAML content lines after "---"
            Returns None if not a valid Docker Compose file.
        """
        metadata = self.get_compose_metadata(source_file_path)
        if metadata is None:
            return None

        with open(source_file_path) as compose_file:
            lines = compose_file.readlines()

        head_lines, yaml_lines = self._parse_compose_lines(lines)

        return {
            "metadata": metadata,
            "head_lines": head_lines,
            "yaml_lines": yaml_lines,
        }

    def _parse_compose_lines(self, lines: list[str]) -> tuple[list[str], list[str]]:
        """Parse compose file lines into head comments and YAML content.

        Args:
            lines: List of lines from the compose file

        Returns:
            Tuple of (head_lines, yaml_lines)
        """
        head_lines = []
        yaml_lines = []
        yaml_started = False

        for line in lines:
            if yaml_started:
                yaml_lines.append(line)
            elif line.strip() == "---":
                yaml_started = True
            elif line.startswith("# "):
                head_lines.append(line[2:])
            elif line.startswith("#"):
                head_lines.append(line[1:])

        return head_lines, yaml_lines
