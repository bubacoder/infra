"""Module for processing and validating markdown links."""

import os
import re
from pathlib import Path


class LinkProcessor:
    """Class for processing and validating markdown links."""

    def __init__(self, logger, markdown_locations, repository_path, output_content_path):
        """Initialize the LinkProcessor.

        Args:
            logger: Logger instance for logging operations
            markdown_locations: List of (source, target, weight) tuples for markdown file locations
            repository_path: Path to the repository root
            output_content_path: Path to the output directory for generated content
        """
        self.logger = logger
        self.markdown_locations = markdown_locations
        self.repository_path = repository_path
        self.output_content_path = output_content_path

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
            if src.endswith("/") and original_target.is_relative_to(src_path):
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
