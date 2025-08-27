#!/usr/bin/env python3

# Generate token at https://github.com/settings/tokens and set the GITHUB_API_TOKEN environment variable before execution.
# To star all repos referenced in a directory, use e.g.:
#   `./github-extract-links.py ~/repos/infra | ./github-star-repo.py`

import os
from urllib.parse import unquote, urlparse

import requests


def star_github_repo(repo_url: str) -> None:
    """
    Stars a GitHub repository given the repository URL.

    Args:
        repo_url (str): The URL of the GitHub repository to star.
    """
    try:
        parsed_url = urlparse(repo_url)
        repo_path = unquote(parsed_url.path.strip('/'))
        owner, repo_name = repo_path.split('/')

        # Construct the API endpoint URL
        api_url = f"https://api.github.com/user/starred/{owner}/{repo_name}"

        # Set the GitHub API token as an environment variable
        github_token = os.environ.get("GITHUB_API_TOKEN")

        # Make the PUT request to star the repository
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json"
        }
        response = requests.put(api_url, headers=headers)

        # Check the response status code
        if response.status_code == 204:
            print(f"Successfully starred repository: {repo_url}")
        else:
            print(f"Failed to star repository: {repo_url}")
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.text}")
    except Exception as e:
        print(f"Error starring repository: {repo_url}")
        print(e)


def main():
    print("Enter a GitHub repository URL (or press Enter to exit):")
    while True:
        try:
            repo_url = input()
        except (EOFError, KeyboardInterrupt):
            break
        if not repo_url:
            break
        star_github_repo(repo_url)


if __name__ == "__main__":
    main()
