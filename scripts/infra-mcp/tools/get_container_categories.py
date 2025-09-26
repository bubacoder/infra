#!/usr/bin/env python3

import os
import sys
from pathlib import Path

try:
    # Try importing with absolute path first (when imported from server.py)
    from utils.git import get_git_root
except ModuleNotFoundError:
    # If that fails, try relative import (when run as a standalone script)
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from utils.git import get_git_root


class ContainerCategoryFinder:
    """
    A class for finding container categories in the docker directory.
    """

    def __init__(self):
        """
        Initialize the ContainerCategoryFinder.
        """
        self.repo_root = Path(get_git_root())
        self.docker_path = self.repo_root / "docker"

    def _check_docker_dir_exists(self) -> None:
        """
        Check if the Docker directory exists and is a directory.

        Raises:
            FileNotFoundError: If the Docker directory doesn't exist or is not a directory.
        """
        if not self.docker_path.exists() or not self.docker_path.is_dir():
            raise FileNotFoundError(f"Docker directory not found: {self.docker_path}")

    def get_container_categories(self) -> list[str]:
        """
        Get a list of container categories from the docker directory.

        Returns:
            List[str]: A list of directory paths relative to the docker directory.
        """
        categories = []

        try:
            # Ensure docker directory exists
            self._check_docker_dir_exists()

            # Walk through the docker directory recursively
            for root, _dirs, files in os.walk(self.docker_path):
                root_path = Path(root)

                # Check for README.md
                readme_path = root_path.joinpath("README.md")
                has_readme = readme_path.exists() and readme_path.is_file()

                # Check for any yaml files in the current directory
                has_yaml = any(file.lower().endswith(('.yaml', '.yml')) for file in files)

                # Only include directories with both README.md and at least one yaml file
                if has_readme and has_yaml:
                    # Get the path relative to the docker directory
                    rel_path = root_path.relative_to(self.docker_path)
                    # Convert to string and use forward slashes for consistency
                    rel_path_str = str(rel_path).replace('\\', '/')
                    # Add the directory to categories if it's not the root docker directory
                    if rel_path_str != '.':
                        categories.append(rel_path_str)

            return sorted(categories)
        except Exception as e:
            raise RuntimeError(f"Error finding container categories: {str(e)}") from None


def main():
    """
    Run the application: read homepage settings and print dashboard groups.
    """
    try:
        finder = ContainerCategoryFinder()
        categories = finder.get_container_categories()
        for category in categories:
            print(category)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
