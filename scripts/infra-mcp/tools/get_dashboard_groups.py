#!/usr/bin/env python3

import sys
from pathlib import Path

import yaml

# Use relative import for package structure
try:
    from ..utils.git import get_git_root
except ImportError:
    # When run as standalone script, adjust path
    import os

    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from utils.git import get_git_root


class DashboardGroupFinder:
    """
    A class for finding dashboard groups from homepage settings.
    """

    def __init__(self) -> None:
        """
        Initialize the DashboardGroupFinder.
        """
        self.repo_root = Path(get_git_root())
        self.settings_file = self.repo_root / "docker" / "dashboard" / "homepage" / "config" / "settings.yaml"

    def get_dashboard_groups(self, settings_file: Path | None = None) -> list[str]:
        """
        Get a list of dashboard groups from the homepage settings.

        Args:
            settings_file: Path to the settings file. If None, uses default.

        Returns:
            A list of dashboard group names.
        """
        if settings_file is None:
            settings_file = self.settings_file

        with open(settings_file, encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}
            if not isinstance(settings, dict):
                return []

        layout = settings.get("layout") or {}
        if not isinstance(layout, dict):
            return []

        return sorted(layout.keys())


def main() -> None:
    """
    Run the application: read homepage settings and print dashboard groups.
    """
    try:
        finder = DashboardGroupFinder()
        groups = finder.get_dashboard_groups()
        for group_name in groups:
            print(group_name)

    except FileNotFoundError as e:
        print(f"Error: Settings file not found: {e}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
