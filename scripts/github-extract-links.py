#!/usr/bin/env python3

import os
import re
import sys


def extract_github_links(directory: str) -> list[str]:
    github_links: set[str] = set()
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".md") or file.endswith(".yml") or file.endswith(".yaml") or file.endswith(".sh") or file.startswith("Dockerfile"):
                file_path = os.path.join(root, file)
                with open(file_path) as f:
                    content = f.read()
                    # Usernames for user accounts on GitHub can only contain alphanumeric characters and dashes ( - ).
                    links = re.findall(r"https://github.com/([\w.\-\_]+/[\w.\-\_]+)", content)
                    links = trim_git_ending(links)
                    github_links.update(links)
    return list(github_links)


def trim_git_ending(links: list[str]) -> list[str]:
    trimmed_links: list[str] = []
    for link in links:
        if link.endswith(".git"):
            trimmed_links.append(link[:-4])
        else:
            trimmed_links.append(link)
    return trimmed_links


def main():
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = os.getcwd()

    links = extract_github_links(directory)
    for link in links:
        print(f"https://github.com/{link}")


if __name__ == "__main__":
    main()
