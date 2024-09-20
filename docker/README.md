# Docker Services

All the user-facing services in this lab setup are deployed using Docker Containers.

> [Docker](https://www.docker.com/) helps developers build, share, run, and verify applications anywhere — without tedious environment configuration or management.

For additional services to host, check [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted).

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
If possible, avoid any hardcoded configuration values in these files. Use environment variables and init containers for customization.

## Start the services

After configuration, execute on a Docker host to apply the local configuration (based on the hostname):
`task docker:apply` or
`docker/apply-local.sh`

## Updates

Updating the container image tags is automated with [Renovate](https://docs.renovatebot.com/).

Check for updates (only useful for containers not having a fixed version tag):
`task docker:check-updates` or
`docker run --rm -v /var/run/docker.sock:/var/run/docker.sock containrrr/watchtower --run-once --cleanup --monitor-only`

Update containers having non-fixed version tags:
`task docker:update` or
`MODE=UPDATE docker/apply-local.sh`

## Tips

Convert `docker run` commands to [docker compose](https://docs.docker.com/compose/compose-file/) format:
- [Composerize - online tool](https://www.composerize.com/)
- [Composerize - CLI tool](https://github.com/composerize/composerize

Use [ctop](https://github.com/bcicen/ctop) to monitor containers from the command-line.

Use the [Docker VS Code Extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-docker) easy to build, manage, and deploy containerized applications from Visual Studio Code.

Use the [Remote - SSH VS Code Extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-ssh) to work on a remote machine.  
Use the "Remote-SSH: Connect to Host" command to initiate a connection.  
Read more: [Remote Development using SSH](https://code.visualstudio.com/docs/remote/ssh)
