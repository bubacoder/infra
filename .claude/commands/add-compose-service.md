# Add Docker Compose Service

## Variables

APPLICATION_NAME: $ARGUMENTS
APPLICATION_HOMEPAGE: $ARGUMENTS

## Instructions

Implement a container-based service by creating and configuring a Docker Compose file.
Follow the architectural pattern in the docker/guidelines.md file.

Implementation steps:
- Visit the APPLICATION_NAME homepage at APPLICATION_HOMEPAGE and the application's GitHub page (if available).
- Search the homepage and docs for Docker Compose deployment examples. If none are found, fall back to plain Docker examples.
- Based on the application's type, determine which existing category (subfolder under docker/) the application belongs to. Do not create a new category; use "tools" as a fallback.
- Following docker/guidelines.md and the found examples, create the Docker Compose as "docker/<category>/<application>.yaml".
- Ensure the compose file contains a brief description of the project and links to the homepage, GitHub page, and any Docker(-Compose) setup example (if available).
- If the installation guide mentions further improvements (e.g., using an optional external database instead of a built-in one, or enabling SSO), add TODOs for these in the head section of the compose file.
- Also add TODOs for any new environment variables required. If necessary, add them to the "config-example/docker/myhost/.env" file.
- After writing the compose file, run: `pre-commit run --files <docker-compose-filename>` and fix any reported issues.
- Pull the container image(s) with the command `docker/labctl.py service pull <category>/<application>` and verify success.
