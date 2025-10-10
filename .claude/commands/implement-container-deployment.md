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
- Based on these patterns and the found examples on the installation instructions page, create the Docker Compose file and save it as `docker/<category>/<application>.yaml`.
- Ensure the compose file contains a brief description of the project and links to the homepage, GitHub page, and any Docker or Docker Compose setup example (if available).
- If the installation guide suggests enhancements (e.g., using an optional external database instead of a built-in one, or enabling SSO), add TODOs at the top of the compose file.
- If any new environment variables are required for configuration, add them to the `config-example/docker/myhost/.env` file with placeholder values only (do not commit secrets).

### Part 2 - Finishing steps

- After writing the compose file, run `pre-commit run --files <docker-compose-filename>` and resolve any reported issues.
- Validate the compose file with `scripts/labctl.py service config <category>/<application>` and fix any errors or warnings.
- Pull the container image(s) with the command `scripts/labctl.py service pull <category>/<application> --quiet` (with 15 minutes timeout) and verify success.
