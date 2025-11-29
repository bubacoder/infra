#!/usr/bin/env python3

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

import yaml
from docker_scanner import DockerComposeScanner
from git_utils import get_git_root
from link_processor import LinkProcessor


class DocsProcessor:
    """Class for processing documentation files and managing links."""

    def __init__(self, repository_path, output_content_path, verbose=False):
        """Initialize the DocsProcessor.

        Args:
            repository_path: Path to the repository root
            output_content_path: Path to the output directory for generated content
            verbose: Whether to enable verbose logging
        """
        self.repository_path = repository_path
        self.output_content_path = output_content_path

        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        if verbose:
            # Create console handler with a higher log level
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter('  %(levelname)s: %(message)s')
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)
            self.logger.setLevel(logging.DEBUG)

        # Load markdown locations
        self.markdown_locations = self.load_config()

        # Initialize link processor
        self.link_processor = LinkProcessor(
            self.logger,
            self.markdown_locations,
            self.repository_path,
            self.output_content_path
        )

        # Initialize docker scanner
        self.docker_scanner = DockerComposeScanner(self.repository_path, self.logger)

    def load_config(self):
        """Load markdown locations from YAML file."""
        yaml_path = self.repository_path / "docs" / "web" / "update-docs-config.yaml"
        try:
            with open(yaml_path) as yaml_file:
                data = yaml.safe_load(yaml_file)
                return data.get("locations", [])
        except (FileNotFoundError, yaml.YAMLError):
            self.logger.exception("Error loading update-docs-config.yaml")
            sys.exit(1)

    def log_copy(self, source_file_path, target_file_path):
        """Log file copying operation."""
        self.logger.debug(f"{source_file_path} ==> {target_file_path}")

    def create_directory(self, directory):
        """Create directory and any parent directories if they don't exist."""
        directory.mkdir(parents=True, exist_ok=True)

    def delete_directory_content(self, content_path):
        """Delete all content in a directory and recreate the directory."""
        if content_path.exists() and content_path.is_dir():
            shutil.rmtree(content_path)
            self.create_directory(content_path)

    def copy_markdown_file(self, source_file_path, target_file_path, weight=0):
        """Copy and process a markdown file, adding frontmatter and fixing links."""
        with open(source_file_path) as readme_file:
            content = readme_file.read()
            lines = content.splitlines(True)  # Keep line endings

        title_found = False
        processed_lines = []

        # First line starting with "# " will be the title
        for line in lines:
            if not title_found and line.startswith("# "):
                title = line[2:].replace("<!-- omit in toc -->", "").strip()
                processed_lines.append("---\n")
                processed_lines.append(f"title: \"{title}\"\n")
                if weight != 0:
                    processed_lines.append(f"weight: {weight}\n")
                processed_lines.append("---\n")
                title_found = True
            else:
                processed_lines.append(line)

        # Process the content to check and fix links
        processed_content = ''.join(processed_lines)
        processed_content = self.link_processor.process_markdown_content(processed_content, source_file_path, target_file_path)

        with open(target_file_path, "w") as readme_file:
            readme_file.write(processed_content)

    def process_location(self, source_path, target_name, weight=0):
        """Process a location specified in markdown_locations."""
        if source_path.endswith("/"):
            self.process_directory(source_path, target_name, weight)
        else:
            self.process_markdown_file(source_path, target_name, weight)

    def process_directory(self, source_path, target_name, weight=0):
        """Process all markdown files in a directory."""
        source_dir = self.repository_path / source_path
        for file in os.listdir(source_dir):
            if file.endswith(".md"):
                target_filename = "_index.md" if file == "README.md" else file
                self.process_markdown_file(source_path + "/" + file, target_name + "/" + target_filename, weight)

    def process_markdown_file(self, source_path, target_name, weight=0):
        """Process a single markdown file."""
        source_file_path = self.repository_path / source_path
        target_file_path = self.output_content_path / target_name

        self.create_directory(target_file_path.parent)
        self.log_copy(source_file_path, target_file_path)
        self.copy_markdown_file(source_file_path, target_file_path, weight)

    def process_docker_directory(self, docker_path, docker_target_path):
        """Process docker directory containing docker-compose files."""
        source_dir = self.repository_path / docker_path
        target_dir = self.output_content_path / docker_target_path

        self.create_directory(Path(target_dir))

        # Scan all compose files using the scanner
        services = self.docker_scanner.scan_docker_directory(docker_path)

        # Group services by directory to handle READMEs
        directories_processed = set()

        for service in services:
            service_category = service["category"]
            category_path = Path(service_category) if service_category else Path(".")

            # Process README.md for this directory if it exists and we haven't processed it yet
            if service["has_readme"] and service_category not in directories_processed:
                source_readme = source_dir / category_path / "README.md"
                target_readme = target_dir / category_path / "_index.md"

                self.create_directory(target_readme.parent)
                self.log_copy(source_readme, target_readme)
                self.copy_markdown_file(source_readme, target_readme)

                directories_processed.add(service_category)

            # Process the compose file and write markdown
            source_file_path = source_dir / service["file_path"]
            target_file_path = target_dir / Path(service["file_path"]).with_suffix(".md")

            self.create_directory(target_file_path.parent)
            self.log_copy(source_file_path, target_file_path)

            metadata = service["metadata"]
            head_lines = service["head_lines"]
            yaml_lines = service["yaml_lines"]

            # Build markdown content with frontmatter
            processed_lines = ["---\n", f"title: \"{metadata['name']}\"\n"]
            if 'description' in metadata:
                processed_lines.append(f"description: \"{metadata['description']}\"\n")
            if 'icon' in metadata:
                processed_lines.append("params:\n")
                processed_lines.append(f"  icon: \"{metadata['icon_url']}\"\n")
            processed_lines.append("---\n")

            # Add head section (comments from compose file)
            processed_lines.extend(head_lines)

            # Add YAML content in code block if present
            if yaml_lines:
                processed_lines.append("```yaml\n")
                processed_lines.extend(yaml_lines)
                processed_lines.append("```\n")

            # Write the processed markdown file
            with open(target_file_path, "w") as doc_file:
                doc_file.writelines(processed_lines)

    def process(self):
        """Main method to process all files."""
        # Remove the content directory (which only contains generated content)
        self.delete_directory_content(self.output_content_path)

        self.logger.info("Processing Docker Compose stacks")
        self.process_docker_directory("docker", "docker")

        for source, target, weight in self.markdown_locations:
            self.logger.info(f"Processing {source} ==> {target}")
            self.process_location(source, target, weight)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process documentation files.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--repository-path", type=str, help="Specify the path to the repository root")
    parser.add_argument("--output-content-path", type=str, help="Specify the path of the generated content")
    args = parser.parse_args()

    # Get repository and output paths
    repository_path = Path(args.repository_path) if args.repository_path else Path(get_git_root())
    output_content_path = Path(args.output_content_path) if args.output_content_path else repository_path / "docs" / "web" / "src" / "content"

    # Create and run the docs processor
    processor = DocsProcessor(repository_path, output_content_path, args.verbose)
    processor.process()
