# Docker Services

All the user-facing services in this lab setup are deployed using Docker Containers.

https://www.docker.com/

> Docker helps developers build, share, run, and verify applications anywhere — without tedious environment configuration or management.

## Directory structure

- `docker` -- Docker-based service configuration
  - `docker/hosts` -- Host specific service configuration
  - `docker/stacks` -- Docker Compose files organized into categories

## Host-specific configuration

In the `docker/hosts` subfolder multiple Docker hosts can be defined.

Configuration files:
- Host-specific settings: `docker/hosts/<hostname>/.env` -> See [Setting Started -> Configure Docker environment files][setup] for more details. (These files are not committed to the repo - backup them separately!)
- Configure which services to start (`up` function) or stop (`down` function): `docker/hosts/<hostname>/apply.sh`

## Services

The applications/services are defined in the `docker/stacks` folder, ordered by category.  
If possible, avoid any hardcoded configuration values in these files.

## Start the services

After configuration, execute on a Docker host to apply the local configuration (based on the hostname):
`docker/apply-local.sh`

## Updates

Check for updates:
`task docker-check-updates` or
`docker run --rm -v /var/run/docker.sock:/var/run/docker.sock containrrr/watchtower --run-once --cleanup --monitor-only`

Update containers having non-fixed version tags:
`task docker-update` or
`UPDATE=true docker/apply-local.sh`

## Tips

Convert `docker run` commands to [docker compose](https://docs.docker.com/compose/compose-file/) format: [Composerize](https://www.composerize.com/).

Use [ctop](commandline monitoring for containers) to monitor containers from the commandline.

Use the [Docker VS Code extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-docker) easy to build, manage, and deploy containerized applications from Visual Studio Code.
