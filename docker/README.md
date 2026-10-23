# Docker Services

All the user-facing services in this lab setup are deployed using Docker Containers.

> [Docker](https://www.docker.com/) helps developers build, share, run, and verify applications anywhere — without tedious environment configuration or management.

For additional services to host, check [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted).

## Directory structure

- `docker` -- Docker Compose files organized into categories
- `config/docker` -- Host specific service configuration

## Configuration

In the `config/docker` subfolder multiple Docker hosts can be defined.

Configuration files:
- Common settings: `config/docker/.env`
- Common service settings: `config/docker/.env.<service-name>`
- Host settings: `config/docker/<hostname>/.env`
- Host service settings: `config/docker/<hostname>/.env.<service-name>`
- Configure which services to start (`state: up`) or stop (`state: down`): `config/docker/<hostname>/services.yaml`

The configuration files are not committed to the repository. See [Configure Docker
environment files](../docs/manual-setup.md#configure-environment-files) for their
loading order and back them up separately.

## Services

The applications/services are defined in the `docker` folder, ordered by category.  
If possible, avoid any hardcoded configuration values in these files. Use environment variables and init containers for customization.

For file naming, adding or registering a service, environment-variable precedence,
Traefik labels and network/volume conventions, follow the
[Compose architecture and patterns](guidelines.md).

## Service operations

Run these tasks from the repository root on the intended Docker host. Host-wide
commands use `config/docker/<hostname>/services.yaml`:

| Command | Purpose |
| --- | --- |
| `task docker:apply` | Apply the registered service states |
| `task docker:update` | Pull images before applying configured service states |
| `task docker:pull-all` | Pull images for all registered services, including disabled ones |
| `task docker:stop` | Bring down registered services |
| `task docker:apply-update` | Update services, prune old unused images and show restart events |
| `task docker:update-example-env` | Regenerate example environment/configuration files from the local host configuration |

Updating the container image tags is automated with [Renovate](https://docs.renovatebot.com/).
Check mutable image tags with `task docker:check-updates`.

### Container update safety

The repository's [Renovate configuration](../renovate.json) pins image digests
and disables container automerge. Keep the digest when deploying: a tag alone
can resolve to different content after review.
Hash-only updates are disabled: Renovate adds initial digest pins and updates
digests with version changes, but does not refresh the digest of an unchanged
tag. Digest-pinned floating tags such as `v3` or `stable` therefore stay on their
current content until the tag changes or the digest is updated manually.

- **Docker Hub:** Renovate waits seven days after the tag's last push before
  proposing image updates. Missing timestamps block the update.
  The existing Saturday schedule still applies, so updates may wait longer.
- **GHCR and other registries:** updates are ungrouped and require Dependency
  Dashboard approval before Renovate creates a PR, followed by manual merge.
  Before approving/merging, check the upstream release date, the proposed digest,
  and security advisories; wait at least seven days after publication. This is a
  **manual review policy**, not an automatically enforced cooldown.

Use upstream-published Docker Hub equivalents where available. Registry changes
must preserve image content/platforms, not just similar names or tags. An image
signature or a passing vulnerability scan does not guarantee a release is clean.
For a security emergency, explicitly review any exception to the waiting period.

For a single service, use [`labctl.py`](guidelines.md#managing-individual-services-labctlpy)
rather than applying every configured service. Rendered Compose configuration may
contain credentials; do not print or share it without redaction.

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
