#!/usr/bin/env python3
"""Extract GitHub repository links from files in a directory."""

import re
import sys
from pathlib import Path

SCANNABLE_EXTENSIONS: tuple[str, ...] = (".md", ".yml", ".yaml", ".sh")
# Usernames for user accounts on GitHub can only contain alphanumeric characters and dashes ( - ).
GITHUB_REPO_PATTERN = re.compile(r"https://github\.com/([\w.\-_]+/[\w.\-_]+)")


def extract_github_links(directory: Path) -> list[str]:
    """Extract unique GitHub repository links from files in a directory.

    Scans markdown, YAML, shell scripts, and Dockerfiles for GitHub URLs.
    """
    github_links: set[str] = set()

    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue

        if not (file_path.suffix in SCANNABLE_EXTENSIONS or file_path.name.startswith("Dockerfile")):
            continue

        try:
            content = file_path.read_text()
        except (OSError, UnicodeDecodeError):
            continue

        links = GITHUB_REPO_PATTERN.findall(content)
        github_links.update(trim_git_suffix(link) for link in links)

    return list(github_links)


def trim_git_suffix(link: str) -> str:
    """Remove .git suffix from a repository path if present."""
    return link.removesuffix(".git")


def main() -> None:
    """Extract and print GitHub links from the specified directory."""
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

    for link in extract_github_links(directory):
        print(f"https://github.com/{link}")


if __name__ == "__main__":
    main()
