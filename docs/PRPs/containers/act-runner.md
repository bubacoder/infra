## Base information for Act Runner application

Application name: Act Runner (Gitea Runner)
Homepage: https://gitea.com/gitea/runner
GitHub page: https://github.com/go-gitea/gitea (main Gitea project only; runner repo is on Gitea at https://gitea.com/gitea/runner)
Install instructions URL: https://docs.gitea.com/usage/actions/act-runner
Container image(s): gitea/runner:latest (old deprecated image: gitea/act_runner)
Category: dev
Dashboard Icon: https://gitea.com/assets/img/favicon.svg
Dashboard Group: Development
Short description: Runner for Gitea Actions CI/CD
Long description: Gitea Runner (formerly act_runner) is the official runner for Gitea Actions. It connects to a Gitea instance and executes CI/CD workflows in isolated Docker containers, supporting three modes: host-level execution, Docker (bind-mounting the host Docker socket), and Docker-in-Docker (DinD) for full isolation.

## Container deployment

### Docker Compose Configuration

The Gitea documentation provides a Docker Compose example using the (now deprecated) `gitea/act_runner` image. The project has since moved to `gitea/runner`. Use the updated image:

```yaml
services:
  runner:
    image: docker.io/gitea/runner:nightly
    environment:
      CONFIG_FILE: /config.yaml
      GITEA_INSTANCE_URL: "${INSTANCE_URL}"
      GITEA_RUNNER_REGISTRATION_TOKEN: "${REGISTRATION_TOKEN}"
      GITEA_RUNNER_NAME: "${RUNNER_NAME}"
      GITEA_RUNNER_LABELS: "${RUNNER_LABELS}"
    volumes:
      - ./config.yaml:/config.yaml
      - ./data:/data
      - /var/run/docker.sock:/var/run/docker.sock
```

#### Ephemeral Runner Mode

For enhanced security, ephemeral runners register for a single job and tear down after completion:

```yaml
services:
  runner:
    image: docker.io/gitea/runner:nightly
    environment:
      CONFIG_FILE: /config.yaml
      GITEA_INSTANCE_URL: "${INSTANCE_URL}"
      GITEA_RUNNER_REGISTRATION_TOKEN: "${REGISTRATION_TOKEN}"
      GITEA_RUNNER_NAME: "${RUNNER_NAME}"
      GITEA_RUNNER_LABELS: "${RUNNER_LABELS}"
      GITEA_RUNNER_EPHEMERAL: "1"
    volumes:
      - ./config.yaml:/config.yaml
      - /var/run/docker.sock:/var/run/docker.sock
```

No `/data` volume is needed for ephemeral runners since credentials are single-use.

### Image Flavours

Three flavours are available, all from the same Dockerfile:

| Tag | Build Target | Base Image | Docker Daemon | Supervisor | Runs As |
|-----|-------------|------------|--------------|------------|---------|
| `latest` (or `<version>`) | `basic` | Alpine | External (host socket) | tini | root |
| `latest-dind` | `dind` | docker:dind | Bundled (privileged) | s6 | root (privileged) |
| `latest-dind-rootless` | `dind-rootless` | docker:dind-rootless | Bundled (rootless) | s6 | rootless (UID 1000) |

- **basic** (`latest`): Minimal Alpine image, no bundled Docker daemon. Bind-mount the host's Docker socket. Does not need `--privileged`.
- **dind** (`latest-dind`): Bundles its own Docker daemon. Requires `--privileged`. Fully isolated from host daemon.
- **dind-rootless** (`latest-dind-rootless`): Runs both daemon and runner as unprivileged user. Reduced blast radius, but has rootless Docker limitations (networking, cgroups, storage drivers).

### Environment Variables

Required:
- `GITEA_INSTANCE_URL` — URL of the Gitea instance (e.g., `https://gitea.example.com`)
- `GITEA_RUNNER_REGISTRATION_TOKEN` — Token obtained from Gitea admin/runners settings

Optional:
- `GITEA_RUNNER_NAME` — Runner display name (default: hostname)
- `GITEA_RUNNER_LABELS` — Comma-separated labels (e.g., `ubuntu-latest:docker://...`)
- `GITEA_RUNNER_EPHEMERAL` — Set to `1` for single-job ephemeral mode
- `GITEA_RUNNER_ONCE` — Set to `1` to run one job then exit
- `CONFIG_FILE` — Path to YAML config file inside container
- `GITEA_MAX_REG_ATTEMPTS` — Max registration retry attempts
- `RUNNER_STATE_FILE` — Path to runner state file
- `GITEA_RUNNER_REGISTRATION_TOKEN_FILE` — Path to file containing registration token

### Configuration File

Generate a default config:

```bash
docker run --entrypoint="" --rm -it gitea/runner:latest gitea-runner generate-config > config.yaml
```

Key config options (see `config.example.yaml` in the repo for full reference):
- `runner.labels` — Job labels and their container mappings
- `container.network` — Docker network for job containers (bridge, host, or custom)
- `container.privileged` — Run job containers in privileged mode
- `container.options` — Additional Docker container launch options
- `container.valid_volumes` — Allowed volume mount sources
- `cache.host` / `cache.port` — External cache server settings
- `log.log_level` — Runner log level (info, debug, trace)

### Cache Configuration

Each runner starts its own cache server automatically for `actions/cache`. Cache entries are local to that runner. For a shared cache across runners, run a dedicated `cache-server`:

```bash
gitea-runner -c cache-server-config.yaml cache-server
```

With the cache server config:
```yaml
cache:
  dir: /data/actcache
  port: 8088
  external_secret: "replace-with-a-strong-random-secret"
```

Point each runner's config at the cache server:
```yaml
cache:
  external_server: "http://<cache-server-host>:8088/"
  external_secret: "replace-with-a-strong-random-secret"
```

### Security Considerations

1. **Docker Socket Mount**: Bind-mounting `/var/run/docker.sock` gives the runner (and any job it runs) access to the host Docker daemon. Jobs could potentially escape the container. Use the DinD flavour for better isolation.

2. **CVE-2026-58053 (Container Escape)**: A vulnerability exists in act_runner (also present in the renamed runner) where `container.options` from workflow YAML is passed to `HostConfig` even when `privileged: false`. Options like `--pid=host`, `--ipc=host`, `--cap-add=ALL`, `--security-opt seccomp=unconfined` can still be set. Mitigations:
   - Use Docker-in-Docker rootless mode for better isolation
   - Use ephemeral runners for one-shot jobs
   - Do not share Docker-backed runners with untrusted repositories
   - Treat `container.options` as untrusted input

3. **Ephemeral Mode**: Enabling `GITEA_RUNNER_EPHEMERAL=1` ensures each runner registers for exactly one job, reducing credential exposure.

4. **Registration Token**: The registration token allows registering new runners. Protect it and rotate it regularly. Store it in a `.env` file or use `GITEA_RUNNER_REGISTRATION_TOKEN_FILE` to read from a file.

5. **Network Isolation**: Job containers run on a separate Docker network by default (`bridge`). For runners that need to reach the Gitea instance by hostname, consider a custom Docker network.

### AMD GPU Acceleration

None. The Gitea Runner is a CI/CD job orchestrator; it does not perform GPU-accelerated work itself. GPU acceleration for workloads inside job containers (e.g., for model training or video encoding) would be configured at the workflow level within the job container, not at the runner level.

### Further Improvements

- Pin the runner to a specific version tag instead of `nightly` for production stability
- Use the `dind-rootless` flavour for production deployments requiring job isolation
- Configure a shared external cache server across multiple runners to avoid rebuilding on each runner
- Mount runner images from a local registry or mirror to avoid rate limits on Docker Hub
- Set up a dedicated Docker network for the runner and Gitea instance to reduce latency
- Configure `container.valid_volumes` to restrict which host paths job containers can mount
