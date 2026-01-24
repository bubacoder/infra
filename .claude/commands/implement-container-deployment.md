# Deploy Docker Compose Service

## Variables

INSTALL_INSTRUCTIONS_FILE: $ARGUMENTS

## Instructions

Deploy a container-based service by creating and configuring a Docker Compose file.
Use the application details and deployment instructions from the file: INSTALL_INSTRUCTIONS_FILE
Follow closely the architectural patterns described in the `docker/guidelines.md` file.

### Part 1 - Create Docker Compose file

- Read the `docker/guidelines.md` file for the architectural patterns you must follow.
- Read the INSTALL_INSTRUCTIONS_FILE file and use its content to create the compose file in the required structure. Abort if the file is not specified or does not exist.
- If the installation instructions contain steps to fetch the Compose setup and/or environment variables from a git repository:
  - Shallow clone that repository to /tmp/infra/container/<application>/ and look at the referenced compose and .env files there.
  - Use the compose and .env files without any changes.
  - If there are additional configuration files, which are referenced in the compose file, copy them.
  - Keep the cloned repository.
- For each container image used in the deployment, get the most specific tag (e.g. tag "1.2.0" is more specific than "1.2") by using the `get-most-specific-container-tag` MCP tool. Use the tag(s) returned by the tool in the Compose stack.
- Based on these patterns and the found examples on the installation instructions page, create the Docker Compose file and save it as `docker/<category>/<application>/<application>.yaml`.
- Ensure the compose file contains a brief description of the project and links to the homepage, GitHub page, and any Docker or Docker Compose setup example (if available).
- If the installation guide suggests enhancements (e.g., using an optional external database instead of a built-in one, or enabling SSO), add TODOs at the top of the compose file.
- If any new environment variables are required for configuration, add them to the `config-example/docker/myhost/.env` file with placeholder values only (do not commit secrets).

### Part 2 - Finishing steps

- After writing the compose file, run `pre-commit run --files <docker-compose-filename>` and resolve any reported issues.
- Validate the compose file with `scripts/labctl.py service config <category>/<application>` and fix any errors or warnings.
- Pull the container image(s) with the command `scripts/labctl.py service pull <category>/<application> --quiet` (with 15 minutes timeout) and verify success.
