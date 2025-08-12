# Docker Compose Architecture and Patterns

This document outlines the common architecture and patterns used in Docker Compose files for the homelab infrastructure.

## File Structure and Naming Conventions

Each Docker service is defined in its own YAML file with the following structure:

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
- Service metadata at the top with comments for documentation
- Links to official sites, source repositories, and helpful guides
- Service-specific subdirectories for configuration files
- Consistent naming conventions for container names

## Core Infrastructure Components

### Networking

All services use a shared external `proxy` network for communication:

```yaml
networks:
  proxy:
    external: true
```

### Traefik Reverse Proxy

Traefik serves as the central reverse proxy for all services with the following features:

- HTTPS with Let's Encrypt automation via Cloudflare DNS
- HTTP to HTTPS redirection
- HTTP/3 support
- Access control via middleware chains
- Integration with Authelia for SSO
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

#### Authelia SSO Integration

Services requiring authentication use Authelia middleware:

```yaml
traefik.http.routers.service-name.middlewares: localaccess-sso@file
```

#### Access Control Patterns

- `localaccess`: Restricts access to local networks only, default option
- `localaccess-sso`: Restricts access to local networks and requires authentication
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
  homepage.widget.type: widget-type  # Optional
  homepage.widget.url: https://service.${MYDOMAIN}/  # Optional
```

## Environment Variables Management

Environment variables are managed through `.env` files in a cascading priority:

1. Common environment variables: `config/docker/.env`
2. Host-specific variables: `config/docker/<hostname>/.env`
3. Service-specific variables: `config/docker/.env.<service-name>`
4. Host and service-specific variables: `config/docker/<hostname>/.env.<service-name>`

Common environment variables include:

- `MYDOMAIN`: Base domain for all services
- `TIMEZONE`: Timezone setting
- `DOCKER_VOLUMES`: Base path for persistent volumes
- Service-specific credentials and API keys

## Volume Management

Persistent data is stored in volumes following this pattern:

```yaml
volumes:
  - ${DOCKER_VOLUMES}/service-name:/data  # Volumes for data storage, not part of the repository
  - ./service-name/config:/config  # Local configuration files, committed to the repository
```

## Deployment Workflow

Services are deployed using the Taskfile system:

```
task docker:apply       # Deploy all containers
task docker:update      # Update and restart containers
task docker:pull        # Pull latest container images
task docker:stop        # Stop configured containers
```

Under the hood, these tasks use the `docker compose` command with the following pattern:

```bash
docker compose -f "$yaml_file" --env-file "$env_file" up --detach
```

## Service Categories

Services are organized into logical categories:

- **Security**: Traefik, Authelia, Cloudflared, CrowdSec, ...
- **Monitoring**: Prometheus, Grafana, Node-exporter, Uptime-kuma, ...
- **Media**: Jellyfin, Metube, Navidrome, Calibre, ...
- **Storage**: MinIO, Syncthing, FileSharing, ...
- **AI Tools**: Ollama, Open-WebUI, LiteLLM, AutogenStudio, ...
- **Tools**: Guacamole, Vaultwarden, SearXNG, ...

## Template for New Services

When creating a new service, use this template:

```yaml
# Brief description of the service
#
# 🏠 Home: https://service-homepage.com/
# 📦 Source: https://github.com/vendor/service
# 📜 Docs: https://docs.service.com/
---
name: service-name
services:
  service:
    image: vendor/service:tag
    container_name: service-name
    restart: unless-stopped
    environment:
      TZ: ${TIMEZONE}
      # Service-specific variables
    volumes:
      - ${DOCKER_VOLUMES}/service-name:/data
      - ./service-name/config:/config  # If needed
    networks:
      - proxy
    labels:
      traefik.enable: true
      traefik.http.routers.service-name.middlewares: middleware-name@file
      traefik.http.services.service-name.loadbalancer.server.port: PORT
      homepage.group: Category
      homepage.name: Service Name
      homepage.icon: service-icon.png
      homepage.href: https://service.${MYDOMAIN}/
      homepage.description: "Service description"

networks:
  proxy:
    external: true
```
