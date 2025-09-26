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
      - proxy  # Main network
      - security-authelia  # Isolated service networks
      - security-wg-easy
      - tools-vaultwarden
      # ... other isolated networks
```

And in the networks section of the same file, all these external networks must be defined:

```yaml
networks:
  proxy:  # Main network
    external: true
  security-authelia:  # Isolated service networks
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
task docker:pull-all    # Pull latest container images
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
# Brief description of the service in 1 to 3 sentences
#
# 🏠 Home: https://service-homepage.com/
# 📦 Source: https://github.com/vendor/service
# 📜 Docs: https://docs.service.com/
---
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
