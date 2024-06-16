# Docker

https://www.docker.com/

> Docker helps developers build, share, run, and verify applications anywhere — without tedious environment configuration or management.

## Host-specific configuration

In the `docker/hosts` subfolder multiple Docker hosts can be defined.

Configuration files:
- Host-specific settings: `docker/hosts/<hostname>/.env` (These files are not included in the repo - backup them separately!)
- Configure which services to start (`up` function) or stop (`down` function): `docker/hosts/<hostname>/apply.sh`

Create example `.env` file from a host configuration:
`scripts/create-env-example.py docker/hosts/nest/.env > docker/hosts/example/.env`

## Services

The applications/services are defined in the `docker/stacks` folder, ordered by category.  
If possible, avoid any hardcoded configuration values in these files.

## Start the services

After configuration, execute on a Docker host to apply the local configuration (based on the hostname):
`docker/apply-local.sh`

## Updates

Check for updates:
`docker run --rm -v /var/run/docker.sock:/var/run/docker.sock containrrr/watchtower --run-once --cleanup --monitor-only`

Update containers having non-fixed version tags:
`UPDATE=true docker/apply-local.sh`

## Tips

Convert `docker run` commands to [docker compose](https://docs.docker.com/compose/compose-file/) format: [Composerize](https://www.composerize.com/)
