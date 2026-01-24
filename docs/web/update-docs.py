#!/usr/bin/env python3
"""Process documentation files and Docker Compose stacks for Hugo site generation."""

import argparse
import logging
import shutil
import sys
from pathlib import Path

import yaml
from docker_scanner import DockerComposeScanner
from git_utils import get_git_root
from link_processor import LinkProcessor


class DocsProcessor:
    """Process documentation files and manage links."""

    def __init__(
        self,
        repository_path: Path,
        output_content_path: Path,
        verbose: bool = False,
    ):
        """Initialize the DocsProcessor.

        Args:
            repository_path: Path to the repository root
            output_content_path: Path to the output directory for generated content
            verbose: Whether to enable verbose logging
        """
        self.repository_path = repository_path
        self.output_content_path = output_content_path
        self.logger = self._setup_logging(verbose)
        self.markdown_locations = self._load_config()
        self.link_processor = LinkProcessor(
            self.logger,
            self.markdown_locations,
            self.repository_path,
            self.output_content_path,
        )
        self.docker_scanner = DockerComposeScanner(self.repository_path, self.logger)

    def _setup_logging(self, verbose: bool) -> logging.Logger:
        """Configure and return logger instance.

        Args:
            verbose: Whether to enable debug logging

        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG if verbose else logging.INFO)

        if verbose:
            handler = logging.StreamHandler()
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("  %(levelname)s: %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _load_config(self) -> list[tuple[str, str, int]]:
        """Load markdown locations from YAML configuration file.

        Returns:
            List of tuples containing (source_path, target_path, weight)

        Raises:
            SystemExit: If configuration file cannot be loaded
        """
        config_path = self.repository_path / "docs" / "web" / "update-docs-config.yaml"
        try:
            with config_path.open() as config_file:
                data = yaml.safe_load(config_file)
                return data.get("locations", [])
        except FileNotFoundError:
            self.logger.exception(f"Configuration file not found: {config_path}")
            sys.exit(1)
        except yaml.YAMLError:
            self.logger.exception(f"Invalid YAML in configuration file: {config_path}")
            sys.exit(1)

    def _log_copy(self, source_path: Path, target_path: Path) -> None:
        """Log file copying operation.

        Args:
            source_path: Source file path
            target_path: Target file path
        """
        self.logger.debug(f"{source_path} ==> {target_path}")

    @staticmethod
    def _ensure_directory(directory: Path) -> None:
        """Create directory and parent directories if they don't exist.

        Args:
            directory: Directory path to create
        """
        directory.mkdir(parents=True, exist_ok=True)

    def _clear_directory(self, directory: Path) -> None:
        """Delete all content in directory and recreate it.

        Args:
            directory: Directory path to clear
        """
        if directory.exists() and directory.is_dir():
            shutil.rmtree(directory)
            self._ensure_directory(directory)

    def _add_frontmatter_to_lines(
        self,
        lines: list[str],
        weight: int = 0,
    ) -> list[str]:
        """Add Hugo frontmatter to markdown lines, extracting title from first heading.

        Args:
            lines: List of markdown lines
            weight: Hugo weight parameter for ordering

        Returns:
            List of lines with frontmatter added
        """
        processed_lines = []
        title_found = False

        for line in lines:
            if not title_found and line.startswith("# "):
                title = line[2:].replace("<!-- omit in toc -->", "").strip()
                processed_lines.extend(
                    [
                        "---\n",
                        f'title: "{title}"\n',
                    ]
                )
                if weight != 0:
                    processed_lines.append(f"weight: {weight}\n")
                processed_lines.append("---\n")
                title_found = True
            else:
                processed_lines.append(line)

        return processed_lines

    def _process_markdown_file(
        self,
        source_path: Path,
        target_path: Path,
        weight: int = 0,
    ) -> None:
        """Process markdown file: add frontmatter and fix links.

        Args:
            source_path: Source markdown file path
            target_path: Target markdown file path
            weight: Hugo weight parameter for ordering
        """
        with source_path.open() as source_file:
            content = source_file.read()
            lines = content.splitlines(keepends=True)

        processed_lines = self._add_frontmatter_to_lines(lines, weight)
        processed_content = "".join(processed_lines)
        processed_content = self.link_processor.process_markdown_content(
            processed_content,
            source_path,
            target_path,
        )

        with target_path.open("w") as target_file:
            target_file.write(processed_content)

    def _process_markdown_location(
        self,
        source_relative: str,
        target_relative: str,
        weight: int = 0,
    ) -> None:
        """Process a markdown location (file or directory).

        Args:
            source_relative: Source path relative to repository root
            target_relative: Target path relative to output content directory
            weight: Hugo weight parameter for ordering
        """
        if source_relative.endswith("/"):
            self._process_directory(source_relative, target_relative, weight)
        else:
            self._process_single_file(source_relative, target_relative, weight)

    def _process_directory(
        self,
        source_relative: str,
        target_relative: str,
        weight: int = 0,
    ) -> None:
        """Process all markdown files in a directory.

        Args:
            source_relative: Source directory path relative to repository root
            target_relative: Target directory path relative to output content directory
            weight: Hugo weight parameter for ordering
        """
        source_dir = self.repository_path / source_relative

        for filename in source_dir.iterdir():
            if filename.suffix != ".md":
                continue

            target_filename = "_index.md" if filename.name == "README.md" else filename.name
            source_file_path = f"{source_relative}{filename.name}"
            target_file_path = f"{target_relative}/{target_filename}"
            self._process_single_file(source_file_path, target_file_path, weight)

    def _process_single_file(
        self,
        source_relative: str,
        target_relative: str,
        weight: int = 0,
    ) -> None:
        """Process a single markdown file.

        Args:
            source_relative: Source file path relative to repository root
            target_relative: Target file path relative to output content directory
            weight: Hugo weight parameter for ordering
        """
        source_path = self.repository_path / source_relative
        target_path = self.output_content_path / target_relative

        self._ensure_directory(target_path.parent)
        self._log_copy(source_path, target_path)
        self._process_markdown_file(source_path, target_path, weight)

    def _build_service_frontmatter(self, metadata: dict) -> list[str]:
        """Build Hugo frontmatter for a service.

        Args:
            metadata: Service metadata dictionary

        Returns:
            List of frontmatter lines

        Raises:
            ValueError: If metadata is missing required 'name' key
        """
        if "name" not in metadata:
            raise ValueError(f"Metadata missing required 'name' key: {metadata}")

        lines = [
            "---\n",
            f'title: "{metadata["name"]}"\n',
        ]

        if "description" in metadata:
            lines.append(f'description: "{metadata["description"]}"\n')

        if "icon" in metadata:
            lines.extend(
                [
                    "params:\n",
                    f'  icon: "{metadata["icon_url"]}"\n',
                ]
            )

        lines.append("---\n")
        return lines

    def _write_service_markdown(
        self,
        target_path: Path,
        metadata: dict,
        head_lines: list[str],
        yaml_lines: list[str],
    ) -> None:
        """Write service markdown file with frontmatter and content.

        Args:
            target_path: Target markdown file path
            metadata: Service metadata dictionary
            head_lines: Comment lines from compose file
            yaml_lines: YAML content lines from compose file
        """
        lines = self._build_service_frontmatter(metadata)
        lines.extend(head_lines)

        if yaml_lines:
            lines.append("```yaml\n")
            lines.extend(yaml_lines)
            lines.append("```\n")

        with target_path.open("w") as target_file:
            target_file.writelines(lines)

    def _process_docker_services(
        self,
        source_dir: Path,
        target_dir: Path,
        docker_path: str,
    ) -> None:
        """Process Docker Compose services and generate documentation.

        Args:
            source_dir: Source docker directory path
            target_dir: Target output directory path
            docker_path: Relative path to docker directory
        """
        self._ensure_directory(target_dir)
        services = self.docker_scanner.scan_docker_directory(docker_path)
        processed_categories = set()

        for service in services:
            category = service["category"]
            category_path = Path(category) if category else Path(".")

            # Process category README once per category
            if service["has_readme"] and category not in processed_categories:
                source_readme = source_dir / category_path / "README.md"
                target_readme = target_dir / category_path / "_index.md"

                self._ensure_directory(target_readme.parent)
                self._log_copy(source_readme, target_readme)
                self._process_markdown_file(source_readme, target_readme)
                processed_categories.add(category)

            # Process service compose file
            source_compose = source_dir / service["file_path"]
            target_markdown = target_dir / Path(service["file_path"]).parent.with_suffix(".md")

            self._ensure_directory(target_markdown.parent)
            self._log_copy(source_compose, target_markdown)
            self._write_service_markdown(
                target_markdown,
                service["metadata"],
                service["head_lines"],
                service["yaml_lines"],
            )

    def process(self) -> None:
        """Process all documentation files and Docker services."""
        self._clear_directory(self.output_content_path)

        self.logger.info("Processing Docker Compose stacks")
        source_dir = self.repository_path / "docker"
        target_dir = self.output_content_path / "docker"
        self._process_docker_services(source_dir, target_dir, "docker")

        for source, target, weight in self.markdown_locations:
            self.logger.info(f"Processing {source} ==> {target}")
            self._process_markdown_location(source, target, weight)


def main() -> None:
    """Main entry point for the documentation processor."""
    parser = argparse.ArgumentParser(description="Process documentation files and Docker Compose stacks for Hugo.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--repository-path", type=str, help="Path to the repository root")
    parser.add_argument("--output-content-path", type=str, help="Path for generated content output")
    args = parser.parse_args()

    repository_path = Path(args.repository_path) if args.repository_path else Path(get_git_root())
    output_content_path = Path(args.output_content_path) if args.output_content_path else repository_path / "docs" / "web" / "src" / "content"

    processor = DocsProcessor(repository_path, output_content_path, args.verbose)
    processor.process()


if __name__ == "__main__":
    main()
