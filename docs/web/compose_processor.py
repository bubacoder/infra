"""Module for processing Docker Compose files and extracting metadata."""

import logging

import yaml


class ComposeFileProcessor:
    """Class for processing Docker Compose files and extracting metadata."""

    def __init__(self, logger=None):
        """Initialize the ComposeFileProcessor.

        Args:
            logger: Logger instance for logging messages. If None, creates a new logger.
        """
        self.logger = logger or logging.getLogger(__name__)

    def get_compose_metadata(self, file_path):
        """Extract metadata from a docker-compose file.

        Args:
            file_path: Path to the docker-compose file

        Returns:
            dict: Dictionary containing name, description, icon and icon URL from homepage labels
        """
        try:
            with open(file_path) as stream:
                compose_dict = yaml.safe_load(stream)
                if compose_dict is None:
                    return {}

            # Handle case where YAML is a list or not a dict
            if not isinstance(compose_dict, dict):
                self.logger.warning(f"Skipping {file_path}: root element is not a dictionary")
                return {}

            services = compose_dict.get("services", {})

            # Handle case where services is not a dict (invalid compose format)
            if not isinstance(services, dict):
                self.logger.warning(f"Skipping {file_path}: services element is not a dictionary")
                return {}

            for service in services.values():
                labels = service.get("labels", {})
                homepage_name = labels.get("homepage.name", "")
                homepage_description = labels.get("homepage.description", "")
                homepage_icon = labels.get("homepage.icon", "")
                icon_url = f"https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/{homepage_icon}" if homepage_icon else ""

                if homepage_icon or homepage_description or homepage_name:
                    if not homepage_name:
                        homepage_name = file_path.stem.capitalize()

                    return {
                        "name": homepage_name,
                        "description": homepage_description,
                        "icon": homepage_icon,
                        "icon_url": icon_url,
                    }

            # No matching labels found in any service
            return {}  # noqa: TRY300
        except yaml.YAMLError:
            self.logger.exception("YAML parsing error")
            return {}

    def extract_compose_file_data(self, source_file_path):
        """Extract all information from a docker-compose file.

        Args:
            source_file_path: Path to the docker-compose file

        Returns:
            dict with keys:
            - metadata: dict containing name, description, icon
            - head_lines: list of comment lines before "---"
            - yaml_lines: list of YAML content lines after "---"
        """
        # Get metadata from compose file
        metadata = self.get_compose_metadata(source_file_path)

        # Return no data if metadata is empty (not a Docker Compose file)
        if not metadata:
            return {}

        # Read all lines from the compose file
        with open(source_file_path) as compose_file:
            lines = compose_file.readlines()

        # Parse lines to extract head section and YAML content
        head_lines = []
        yaml_lines = []
        yaml_started = False

        for line in lines:
            if yaml_started:
                yaml_lines.append(line)
            elif line.startswith("# "):
                head_lines.append(line[2:])
            elif line.startswith("#"):
                head_lines.append(line[1:])
            elif line.strip() == "---":
                yaml_started = True

        return {
            "metadata": metadata,
            "head_lines": head_lines,
            "yaml_lines": yaml_lines,
        }
