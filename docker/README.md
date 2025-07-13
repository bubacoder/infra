# Docker Services

All the user-facing services in this lab setup are deployed using Docker Containers.

> [Docker](https://www.docker.com/) helps developers build, share, run, and verify applications anywhere — without tedious environment configuration or management.

For additional services to host, check [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted).

## Directory structure

- `docker` -- Docker Compose files organized into categories
- `config/docker` -- Host specific service configuration

## Host-specific configuration

In the `config/docker` subfolder multiple Docker hosts can be defined.

Configuration files:
- Host-specific settings: `config/docker/<hostname>/.env` -> See [Setting Started -> Configure Docker environment files][setup] for more details. (These files are not committed to the repo - backup them separately!)
- Configure which services to start (`state: up`) or stop (`state: down`): `config/docker/<hostname>/services.yaml`

## Services

The applications/services are defined in the `docker` folder, ordered by category.  
If possible, avoid any hardcoded configuration values in these files. Use environment variables and init containers for customization.

## Start the services

After configuration, execute on a Docker host to apply the local configuration (based on the hostname):
`task docker:apply` or `docker/labctl.py config apply`

## Updates

Updating the container image tags is automated with [Renovate](https://docs.renovatebot.com/).

Check for updates (only useful for containers not having a fixed version tag): `task docker:check-updates`

Update containers having non-fixed version tags: `task docker:update`

## Tips

### Compose

Convert `docker run` commands to [docker compose](https://docs.docker.com/compose/compose-file/) format:
- [Composerize - Online](https://www.composerize.com/)
- [Composerize - CLI tool](https://github.com/composerize/composerize)

### Monitoring

Use [ctop](https://github.com/bcicen/ctop) to monitor containers from the command-line.

### Copy a Docker image from local machine to a remote host

Prerequisites:
- SSH access: Set up with `ssh-copy-id user@remotehost`
- Docker group: Both local and remote users must be in the docker group: `sudo usermod -aG docker $USER`

List images:
```sh
docker images
```

Transfer:
```sh
docker save app:1.0 | gzip | DOCKER_HOST=ssh://user@remotehost docker load
```

Replace `user@remotehost` as needed.
This command saves, compresses, transfers, and loads the image directly on the remote host.

Reference: [How to copy Docker images from one host to another without using a repository](https://stackoverflow.com/questions/23935141/how-to-copy-docker-images-from-one-host-to-another-without-using-a-repository)

### Useful Visual Studio Code Extensions

Use the [Docker VS Code Extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-docker) easy to build, manage, and deploy containerized applications from Visual Studio Code.

Use the [Remote - SSH VS Code Extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-ssh) to work on a remote machine.  
Initiate a connection with the "Remote-SSH: Connect to Host" command.  
Read more: [Remote Development using SSH](https://code.visualstudio.com/docs/remote/ssh)
