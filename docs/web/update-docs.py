#!/usr/bin/env python3

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


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

    def extract_relative_links(self, content):
        """Extract all relative markdown links from content.

        Returns:
            list of tuples (link_text, link_url).
        """
        # Match markdown links [text](url) but only when url doesn't start with http/https/#
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^\)]+)\)')
        links = []

        for match in link_pattern.finditer(content):
            link_text, link_url = match.groups()
            # Filter only relative links (not http, https, or anchor links)
            if not (link_url.startswith("http://") or
                    link_url.startswith("https://") or
                    link_url.startswith("#") or
                    link_url.startswith("mailto:")):
                links.append((link_text, link_url))

        return links

    def is_valid_link(self, source_file_path, link_url):
        """Check if a relative link in a markdown file points to an existing file."""
        # Get the directory of the source file
        source_dir = source_file_path.parent

        # Remove any anchor part of the link (#section-id)
        link_path = link_url.split("#")[0]

        # Handle empty links (usually anchors in the same file)
        if not link_path:
            return True

        # Resolve the path relative to the source file
        target_path = (source_dir / link_path).resolve()

        return target_path.exists()

    def update_relative_link(self, link_url, source_path, target_path):
        """Update a relative link to account for directory structure changes.

        Args:
            link_url: The original relative link URL
            source_path: Original file path
            target_path: New file path

        Returns:
            Updated link URL
        """
        # Remove any anchor part and store it
        if "#" in link_url:
            link_path, anchor = link_url.split("#", 1)
            anchor = "#" + anchor
        else:
            link_path = link_url
            anchor = ""

        # If it's an empty link (just an anchor), return as is
        if not link_path:
            return link_url

        # Get the original link target absolute path
        source_dir = source_path.parent
        original_target = (source_dir / link_path).resolve()

        # Find the target path in markdown_locations
        for src, tgt, _ in self.markdown_locations:
            src_path = self.repository_path / src

            # If the original target is inside this source directory
            if src.endswith("/") and str(original_target).startswith(str(src_path)):
                # Calculate the relative path within the source directory
                rel_path = original_target.relative_to(src_path)

                # Construct the new target path
                new_target = Path(tgt) / rel_path

                # Calculate relative path from target_path's parent to new_target
                new_relative_link = os.path.relpath(
                    self.output_content_path / new_target,
                    target_path.parent
                )

                self.logger.debug(f"Updated link from {link_url} to {new_relative_link}{anchor}")
                return new_relative_link + anchor

            # If the original target matches a specific file
            elif not src.endswith("/") and original_target == src_path:
                new_target = tgt

                # Calculate relative path from target_path's parent to new_target
                new_relative_link = os.path.relpath(
                    self.output_content_path / new_target,
                    target_path.parent
                )

                self.logger.debug(f"Updated link from {link_url} to {new_relative_link}{anchor}")
                return new_relative_link + anchor

        # If we couldn't find a match in markdown_locations, the link might be broken
        # or pointing to a file not included in the documentation
        self.logger.warning(f"Could not update link: {link_url} - target file not found in markdown locations")
        return link_url

    def process_markdown_content(self, content, source_file_path, target_file_path):
        """Process markdown content to check and fix relative links."""
        links = self.extract_relative_links(content)

        if not links:
            return content

        result = content
        for link_text, link_url in links:
            # Check if the link is valid
            if not self.is_valid_link(source_file_path, link_url):
                self.logger.warning(f"Broken link in {source_file_path}: [{link_text}]({link_url})")
            else:
                self.logger.debug(f"Found valid link in {source_file_path}: [{link_text}]({link_url})")

            # Update the link to account for directory structure changes
            updated_link = self.update_relative_link(link_url, source_file_path, target_file_path)

            if updated_link != link_url:
                # Replace the link in the content
                original_link_pattern = re.escape(f"[{link_text}]({link_url})")
                new_link = f"[{link_text}]({updated_link})"
                result = re.sub(original_link_pattern, new_link, result)

        return result

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
        processed_content = self.process_markdown_content(processed_content, source_file_path, target_file_path)

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

    def process_docker_stack_index(self, source_dir, target_dir, root, file):
        """Process a docker stack README.md file."""
        source_file_path = Path(root) / file
        relative_path = source_file_path.relative_to(source_dir).with_name("_index.md")
        target_file_path = Path(target_dir) / relative_path

        self.create_directory(target_file_path.parent)
        self.log_copy(source_file_path, target_file_path)
        self.copy_markdown_file(source_file_path, target_file_path)

    def get_icon_url(self, icon):
        """Get the URL for a dashboard icon."""
        return f"https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/{icon}" if icon else ""

    def get_compose_metadata(self, file_path):
        """Extract metadata from a docker-compose file."""
        try:
            with open(file_path) as stream:
                compose_dict = yaml.safe_load(stream)
                if compose_dict is None:
                    return {}

            services = compose_dict.get("services", {})

            for service in services.values():
                labels = service.get("labels", {})
                homepage_name = labels.get("homepage.name", "")
                homepage_description = labels.get("homepage.description", "")
                homepage_icon = labels.get("homepage.icon", "")

                if homepage_icon or homepage_description or homepage_name:
                    return {
                        "name": homepage_name,
                        "description": homepage_description,
                        "icon": homepage_icon,
                    }

            # No matching labels found in any service
            return {}  # noqa: TRY300
        except yaml.YAMLError:
            self.logger.exception("YAML parsing error")
            return {}

    def process_docker_compose_file(self, source_dir, target_dir, root, file):
        """Process a docker-compose file."""
        # Skip non-compose files (like .env files)
        if not file.endswith((".yml", ".yaml")):
            return

        source_file_path = Path(root) / file
        relative_path = source_file_path.relative_to(source_dir)
        target_file_path = Path(target_dir) / relative_path.with_suffix(".md")

        self.create_directory(target_file_path.parent)
        self.log_copy(source_file_path, target_file_path)

        metadata = self.get_compose_metadata(source_file_path)
        metadata.setdefault("name", source_file_path.stem.capitalize())

        with open(source_file_path) as compose_file:
            lines = compose_file.readlines()

        yaml_started = False
        processed_lines = ["---\n", f"title: \"{metadata['name']}\"\n"]
        if 'description' in metadata:
            processed_lines.append(f"description: \"{metadata['description']}\"\n")
        if 'icon' in metadata:
            processed_lines.append("params:\n")
            processed_lines.append(f"  icon: \"{self.get_icon_url(metadata['icon'])}\"\n")
        processed_lines.append("---\n")

        for line in lines:
            if yaml_started:
                processed_lines.append(line)
            elif line.startswith("# "):
                processed_lines.append(line[2:])
            elif line.startswith("#"):
                processed_lines.append(line[1:])
            elif line.strip() == "---":
                yaml_started = True
                processed_lines.append("```yaml\n")

        if yaml_started:
            processed_lines.append("```\n")
            with open(target_file_path, "w") as doc_file:
                doc_file.writelines(processed_lines)

    def process_docker_directory(self, docker_path, docker_target_path):
        """Process docker directory containing docker-compose files."""
        source_dir = self.repository_path / docker_path
        target_dir = self.output_content_path / docker_target_path

        self.create_directory(Path(target_dir))

        # Walk through the source directory recursively
        for root, _, files in os.walk(source_dir):
            if "README.md" in files:
                self.process_docker_stack_index(source_dir, target_dir, root, "README.md")
                for file in files:
                    if file.endswith((".yaml", ".yml")):
                        self.process_docker_compose_file(source_dir, target_dir, root, file)

    def process(self):
        """Main method to process all files."""
        # Remove the content directory (which only contains generated content)
        self.delete_directory_content(self.output_content_path)

        self.logger.info("Processing Docker Compose stacks")
        self.process_docker_directory("docker", "docker")

        for source, target, weight in self.markdown_locations:
            self.logger.info(f"Processing {source} ==> {target}")
            self.process_location(source, target, weight)


def get_git_root() -> str:
    """Get the git repository root directory.

    Returns:
        str: The absolute path to the git repository root directory.

    Raises:
        RuntimeError: If git executable is not found or not in a git repository.
    """
    git_cmd = shutil.which("git")
    if git_cmd is None:
        raise RuntimeError("Git not found on PATH") from None
    try:
        result = subprocess.run(  # noqa: S603
            [git_cmd, "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            check=True,
            text=True,
        )
    except FileNotFoundError:
        raise RuntimeError("Git executable not found. Please install Git and ensure it is on your PATH.") from None
    except subprocess.CalledProcessError:
        raise RuntimeError("Unable to locate git repository. Are you running this inside a Git repo?") from None
    return result.stdout.strip()


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
