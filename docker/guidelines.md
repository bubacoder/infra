# Docker Compose Architecture and Patterns

This document outlines the common architecture and patterns used in Docker Compose files for the homelab infrastructure.

## File Structure and Naming Conventions

Each Docker service has its own directory containing documentation and Compose configuration:

```text
docker/<category>/<service-name>/
├── README.md                      # Description, setup/operations, references, TODOs
├── <service-name>.yaml            # Base Docker Compose configuration
├── <service-name>-amdgpu.yaml     # Optional hardware-specific Compose override
└── config/                        # Optional tracked application configuration
```

`<category>` is an existing category under `docker/` (e.g. `ai`, `tools`, `media/video`).
The base Compose file lives at `docker/<category>/<service-name>/<service-name>.yaml`
and contains runtime configuration, not a leading documentation comment block:

```yaml
---
name: service-name
services:
  main-service:
    image: vendor/image:tag
    container_name: service-name
    restart: unless-stopped
    # other configuration...

  # Optional supporting services
  supporting-service:
    # configuration...

networks:
  proxy:
    external: true
```

**Common Practices:**
- Keep descriptions, setup instructions, links, and TODOs in the service's `README.md`
- Keep only configuration-specific comments beside the relevant YAML settings
- Service-specific subdirectories for configuration files
- Consistent naming conventions for container names

### Service README Structure

Every new service must include `README.md` beside its base Compose file. Use this structure:

1. **Description:** Start with a short explanation of the application and its purpose
   (typically 1–3 sentences). An application-name heading is optional.
2. **TODOs, when applicable:** Record outstanding setup or follow-up work in the README,
   either next to the relevant section or as `TODO:` lines / a dedicated section.
   Do not add an empty TODO section or move general documentation back into YAML headers.
3. **Setup and operational notes, when applicable:** Document required environment
   variables by name and example-file location, first-run configuration, authentication
   and access restrictions, and any manual steps. Add service-specific sections such as
   GPU acceleration, upgrades, backup, or recovery only when needed. Link to longer
   repository guides rather than duplicating them. Never include real credentials.
4. **`## References`:** Use Markdown links in a bulleted list, with labels such as
   `Home`, `Source`, `Docs`, `Image`, and `Docker Compose`. Include verified links
   collected during research; omit unavailable links instead of inventing them.

Examples: [HTTPBin](tools/httpbin/README.md) for a simple service,
[Jellyfin](media/video/jellyfin/README.md) and [Ollama](ai/ollama/README.md) for GPU
instructions, and [Authentik](security/authentik/README.md) for secrets, SSO, and recovery.
The documentation exporter includes the service README alongside its Compose configuration.

## Core Infrastructure Components

### Networking

#### Shared Proxy Network

By default, most services connect to the shared external `proxy` network for communication:

```yaml
networks:
  proxy:
    external: true
```

#### Isolated Networks for Sensitive Services

Sensitive services (like backup systems, password managers, VPN services) should use isolated networks to prevent direct communication between services, with only Traefik able to connect to them:

```yaml
# Service YAML file - isolated network definition
networks:
  service-category-name:
    external: true

# Service configuration
services:
  service:
    # ... other configuration
    networks:
      - service-category-name  # Instead of 'proxy'
    labels:
      traefik.enable: true
      traefik.docker.network: service-category-name  # Tell Traefik which network to use
      # ... other labels
```

Traefik must be connected to all isolated networks to route traffic:

```yaml
# traefik.yaml
services:
  traefik:
    # ... other configuration
    networks:
      # Main network
      - proxy
      # Isolated service networks:
      - security-authentik
      - security-wg-easy
      - tools-vaultwarden
      # ... other isolated networks
```

And in the networks section of the same file, all these external networks must be defined:

```yaml
networks:
  # Main network
  proxy:
    external: true
  # Isolated service networks
  security-authentik:
    external: true
  security-wg-easy:
    external: true
  tools-vaultwarden:
    external: true
  # ... other isolated networks
```

This architecture ensures that:
1. Sensitive services can only communicate with Traefik, not with each other
2. Services in isolated networks are not reachable from the shared proxy network
3. All external access still flows through Traefik's security controls

### Traefik Reverse Proxy

Traefik serves as the central reverse proxy for all services with the following features:

- HTTPS with Let's Encrypt automation via Cloudflare DNS
- HTTP to HTTPS redirection
- HTTP/3 support
- Access control via middleware chains
- Integration with Authentik
- Integration with CrowdSec for security
- Docker provider for automatic service discovery

#### Traefik Labels Pattern

Services expose themselves to Traefik using labels:

```yaml
labels:
  traefik.enable: true
  traefik.http.routers.service-name.rule: Host(`service.${MYDOMAIN}`)
  traefik.http.routers.service-name.middlewares: middleware-name@file
  traefik.http.services.service-name.loadbalancer.server.port: 8080
```

### Authentication & Security

#### Authentication Integration

New services start local-only:

```yaml
traefik.http.routers.service-name.middlewares: localaccess@file
```

Onboard SSO separately using
`docker/security/authentik/app-onboarding.md`. Authentik-protected browser routes use
`localaccess-authentik@file`.

#### Access Control Patterns

- `localaccess`: Restricts access to local networks only, default option
- `localaccess-authentik`: Restricts access to local networks and requires Authentik
- `publicaccess`: Available externally with CrowdSec protection

#### Cloudflare Tunnel

External access is provided securely via Cloudflare Tunnel, avoiding direct port exposure.

### Homepage Dashboard Integration

Services are integrated into the Homepage dashboard using labels:

```yaml
labels:
  homepage.group: Category
  homepage.name: Service Name
  homepage.icon: icon-name.png
  homepage.href: https://service.${MYDOMAIN}/
  homepage.description: "Service description"
```

## Environment Variables Management

Environment variables are managed through `.env` files in a cascading priority:

1. Common environment variables: `config/docker/.env`
2. Host-specific variables: `config/docker/<hostname>/.env`
3. Service-specific variables: `config/docker/.env.<service-name>`
4. Host and service-specific variables: `config/docker/<hostname>/.env.<service-name>`

Common environment variables include:

- `PUID`: User Id on the host machine
- `PGID`: Group Id on the host machine
- `TIMEZONE`: Timezone setting
- `MYDOMAIN`: Base domain for all services

Host-specific files contain values such as `DOCKER_VOLUMES` and storage paths.
Service credentials, API keys, and other application settings belong in the
service-specific file, using the host-specific variant when they differ by host.

## Volume Management

Persistent data is stored in volumes following this pattern:

```yaml
volumes:
  - ./service-name/config:/config  # Local configuration files, committed to the repository
  - ${DOCKER_VOLUMES}/service-name:/data  # Volumes for data storage, not part of the repository
```

For data-heavy applications, like database servers, use named volumes instead of bind mounts.

## Deployment Workflow

For host-wide deploy, update, pull and stop commands, see
[Service operations](README.md#service-operations).

Under the hood, `labctl.py` passes each existing file in the documented order to
`docker compose`; later files override earlier values:

```bash
docker compose -f "$yaml_file" \
  --env-file config/docker/.env \
  --env-file config/docker/<hostname>/.env \
  --env-file config/docker/.env.<service-name> \
  --env-file config/docker/<hostname>/.env.<service-name> up --detach
```

### Service Registration

A compose file is not deployed until the service is registered in the host's `config/docker/<hostname>/services.yaml`, listed under its `<category>` with `state: up` (or `down`). `task docker:apply` / `labctl.py` only act on registered services.

When adding or modifying a service:

1. Create or edit its Compose file and README in the appropriate category directory.
2. Register it in the intended host's `services.yaml`.
3. Document required variables and put operator-supplied values in the appropriate
   ignored `.env` files, following [environment-variable precedence](#environment-variables-management).
4. After authorization, deploy that service with `labctl.py service up`, or apply
   the full host configuration with `task docker:apply`.

### Managing Individual Services (`labctl.py`)

Services are addressed as `<category>/<service-name>` (e.g. `ai/ollama`, `media/video/jellyfin`). Manage a single service with:

```bash
scripts/labctl.py service <operation> <category>/<service-name>
```

Operations: `up`, `down`, `restart`, `recreate`, `pull`, `config` (render the resolved compose config), `logs`.

```bash
scripts/labctl.py service up security/traefik
scripts/labctl.py service restart ai/ollama
scripts/labctl.py service pull media/video/jellyfin
```

## GPU Acceleration Overrides

Services that support hardware acceleration keep the GPU configuration in a **separate Docker Compose override file** — never in the base compose file, so hosts without a GPU run the base file unchanged.

- The override file is named `docker/<category>/<service>/<service>-<suffix>.yaml` (e.g. `-amdgpu`). `labctl.py` merges it automatically when the host sets `GPU_COMPOSE_SUFFIX=<suffix>` in `config/docker/<hostname>/.env`.
- Because it is a merge override, it repeats the same `name:` and service key as the base file and includes **only the fields that change**.

```yaml
# AMD GPU override (VAAPI video decode/transcode, or ROCm compute)
---
name: service-name
services:
  service-name:
    # image: vendor/service:tag-rocm    # only if the vendor ships a GPU-specific tag (e.g. Ollama :rocm)
    devices:
      - /dev/dri/renderD128:/dev/dri/renderD128   # VAAPI / render node
      # - /dev/kfd:/dev/kfd                        # add for ROCm compute (inference); not needed for VAAPI-only
    group_add:
      - "${GPU_RENDER_GID}"  # render group — numeric GID required (name may not exist in container)
      - "${GPU_VIDEO_GID}"   # video group
```

Document the override in the service's `README.md`: name the override file and
acceleration backend, include the `GPU_COMPOSE_SUFFIX=<suffix>` enable line and
required host environment variables, and list any **manual in-app steps** still
required (e.g. Jellyfin: enable VA-API in Dashboard → Playback → Transcoding;
Frigate: set `hwaccel_args: preset-vaapi` in `config/config.yml`). Keep the override
itself limited to configuration and comments explaining individual settings.
Use the backend and image supported by the target hardware; do not assume every
AMD GPU requires ROCm (the Ollama example uses Vulkan).
See the working examples and their adjacent READMEs:
`docker/media/video/jellyfin/jellyfin-amdgpu.yaml`,
`docker/ai/ollama/ollama-amdgpu.yaml`, `docker/security/frigate/frigate-amdgpu.yaml`.

## Service Categories

Services are organized into logical categories:

- **Security**: Traefik, Authentik, Cloudflared, CrowdSec, ...
- **Monitoring**: Prometheus, Grafana, Node-exporter, Uptime-kuma, ...
- **Media**: Jellyfin, Metube, Navidrome, Calibre, ...
- **Storage**: MinIO, Syncthing, FileSharing, ...
- **AI Tools**: Ollama, Open-WebUI, LiteLLM, AutogenStudio, ...
- **Tools**: Guacamole, Vaultwarden, SearXNG, ...

## Template for New Services

Create both `README.md` and `<service-name>.yaml` in the service directory.
Use the [Service README Structure](#service-readme-structure) above and this
Markdown template, omitting optional sections that do not apply:

```markdown
Brief description of the service in 1 to 3 sentences.

## Setup

Required configuration, environment-variable names and example-file locations,
first-run steps, and access/authentication notes. Do not include real secrets.

TODO: Specific outstanding setup or follow-up work, if any.

## GPU Acceleration

If supported: override filename, backend, host prerequisites, enable setting,
and manual application configuration.

## References

- Home: [Application homepage](https://service-homepage.com/)
- Source: [Source repository](https://github.com/vendor/service)
- Docs: [Official documentation](https://docs.service.com/)
- Image: [Container image](https://registry.example.com/vendor/service)
```

The URLs above are placeholders; replace them with verified links or omit them.
Use this template for the base Compose file, without a documentation header:

```yaml
name: service-name
services:
  service-name:
    image: vendor/service:tag
    container_name: service-name
    restart: unless-stopped
    environment:
      TZ: ${TIMEZONE}
      PUID: ${PUID}  # Host user ID for file ownership (if image supports it)
      PGID: ${PGID}  # Host group ID for file ownership (if image supports it)
      # Service-specific variables
    volumes:
      - ${DOCKER_VOLUMES}/service-name:/data
      - ./service-name/config:/config  # Local configuration files, committed to the repository (if needed)
    networks:
      - proxy  # Or service-specific network for sensitive services
    labels:
      traefik.enable: true
      # If using isolated network, specify which network Traefik should use
      # traefik.docker.network: service-category-name
      traefik.http.routers.service-name.middlewares: middleware-name@file
      traefik.http.services.service-name.loadbalancer.server.port: PORT
      homepage.group: Category
      homepage.name: Service Name
      homepage.icon: service-icon.png
      homepage.href: https://service.${MYDOMAIN}/
      homepage.description: "Service description"

networks:
  proxy:  # Or service-specific network for sensitive services
    external: true
```
