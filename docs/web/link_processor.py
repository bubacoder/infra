"""Module for processing and validating markdown links."""

import logging
import os
import re
from pathlib import Path


class LinkProcessor:
    """Process and validate markdown links in documentation files."""

    def __init__(
        self,
        logger: logging.Logger,
        markdown_locations: list[tuple[str, str, int]],
        repository_path: Path,
        output_content_path: Path,
    ) -> None:
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
        self._link_pattern = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")

    def extract_relative_links(self, content: str) -> list[tuple[str, str]]:
        """Extract all relative markdown links from content.

        Args:
            content: Markdown content to parse

        Returns:
            List of tuples containing (link_text, link_url) for relative links only
        """
        links = []
        for match in self._link_pattern.finditer(content):
            link_text, link_url = match.groups()
            if self._is_relative_link(link_url):
                links.append((link_text, link_url))
        return links

    def _is_relative_link(self, url: str) -> bool:
        """Check if a URL is a relative link.

        Args:
            url: URL to check

        Returns:
            True if the URL is relative (not http/https/mailto/anchor)
        """
        absolute_prefixes = ("http://", "https://", "#", "mailto:")
        return not url.startswith(absolute_prefixes)

    def is_valid_link(self, source_file_path: Path, link_url: str) -> bool:
        """Check if a relative link points to an existing file.

        Args:
            source_file_path: Path to the source markdown file
            link_url: The relative link URL to validate

        Returns:
            True if the link target exists
        """
        link_path = link_url.split("#")[0]

        if not link_path:
            return True

        target_path = (source_file_path.parent / link_path).resolve()
        return target_path.exists()

    def update_relative_link(self, link_url: str, source_path: Path, target_path: Path) -> str:
        """Update a relative link to account for directory structure changes.

        Args:
            link_url: The original relative link URL
            source_path: Original file path
            target_path: New file path

        Returns:
            Updated link URL
        """
        link_path, anchor = self._split_anchor(link_url)

        if not link_path:
            return link_url

        original_target = (source_path.parent / link_path).resolve()
        new_relative_link = self._find_updated_link_path(original_target, target_path, link_url)

        if new_relative_link:
            return new_relative_link + anchor

        self.logger.warning(f"Could not update link: {link_url} - target file not found in markdown locations")
        return link_url

    def _split_anchor(self, link_url: str) -> tuple[str, str]:
        """Split a link URL into path and anchor components.

        Args:
            link_url: The link URL to split

        Returns:
            Tuple of (link_path, anchor) where anchor includes the # prefix
        """
        if "#" in link_url:
            link_path, anchor_text = link_url.split("#", 1)
            return link_path, f"#{anchor_text}"
        return link_url, ""

    def _find_updated_link_path(self, original_target: Path, target_path: Path, link_url: str) -> str | None:
        """Find the updated link path in markdown locations.

        Args:
            original_target: Absolute path to the original link target
            target_path: New file path
            link_url: Original link URL for logging

        Returns:
            Updated relative link path or None if not found
        """
        for src, tgt, _ in self.markdown_locations:
            src_path = self.repository_path / src

            if src.endswith("/") and original_target.is_relative_to(src_path):
                return self._calculate_directory_link(original_target, src_path, tgt, target_path, link_url)

            if not src.endswith("/") and original_target == src_path:
                return self._calculate_file_link(tgt, target_path, link_url)

        return None

    def _calculate_directory_link(
        self,
        original_target: Path,
        src_path: Path,
        tgt: str,
        target_path: Path,
        link_url: str,
    ) -> str:
        """Calculate the updated link path for a directory-based link.

        Args:
            original_target: Absolute path to the original link target
            src_path: Source directory path
            tgt: Target directory string
            target_path: New file path
            link_url: Original link URL for logging

        Returns:
            Updated relative link path
        """
        rel_path = original_target.relative_to(src_path)
        new_target = Path(tgt) / rel_path
        new_relative_link = os.path.relpath(self.output_content_path / new_target, target_path.parent)
        self.logger.debug(f"Updated link from {link_url} to {new_relative_link}")
        return new_relative_link

    def _calculate_file_link(self, tgt: str, target_path: Path, link_url: str) -> str:
        """Calculate the updated link path for a file-based link.

        Args:
            tgt: Target file string
            target_path: New file path
            link_url: Original link URL for logging

        Returns:
            Updated relative link path
        """
        new_relative_link = os.path.relpath(self.output_content_path / tgt, target_path.parent)
        self.logger.debug(f"Updated link from {link_url} to {new_relative_link}")
        return new_relative_link

    def process_markdown_content(self, content: str, source_file_path: Path, target_file_path: Path) -> str:
        """Process markdown content to check and fix relative links.

        Args:
            content: Markdown content to process
            source_file_path: Path to the source markdown file
            target_file_path: Path to the target output file

        Returns:
            Processed markdown content with updated links
        """
        links = self.extract_relative_links(content)

        if not links:
            return content

        result = content
        for link_text, link_url in links:
            self._validate_link(source_file_path, link_text, link_url)
            result = self._update_link_in_content(result, link_text, link_url, source_file_path, target_file_path)

        return result

    def _validate_link(self, source_file_path: Path, link_text: str, link_url: str) -> None:
        """Validate a link and log appropriate messages.

        Args:
            source_file_path: Path to the source markdown file
            link_text: Text of the link
            link_url: URL of the link
        """
        if not self.is_valid_link(source_file_path, link_url):
            self.logger.warning(f"Broken link in {source_file_path}: [{link_text}]({link_url})")
        else:
            self.logger.debug(f"Found valid link in {source_file_path}: [{link_text}]({link_url})")

    def _update_link_in_content(
        self,
        content: str,
        link_text: str,
        link_url: str,
        source_file_path: Path,
        target_file_path: Path,
    ) -> str:
        """Update a link in the content if necessary.

        Args:
            content: Markdown content
            link_text: Text of the link
            link_url: URL of the link
            source_file_path: Path to the source markdown file
            target_file_path: Path to the target output file

        Returns:
            Updated content
        """
        updated_link = self.update_relative_link(link_url, source_file_path, target_file_path)

        if updated_link == link_url:
            return content

        original_link_pattern = re.escape(f"[{link_text}]({link_url})")
        new_link = f"[{link_text}]({updated_link})"
        return re.sub(original_link_pattern, new_link, content)
