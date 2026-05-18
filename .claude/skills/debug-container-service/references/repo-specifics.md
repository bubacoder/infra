# Repo-Specific Patterns for Container Service Debugging

## Service Name Format

Services follow `category/service-name` (or `category/subcategory/service-name`).

| Service name | Compose file location |
|---|---|
| `ai/open-webui` | `docker/ai/open-webui/open-webui.yaml` |
| `security/traefik` | `docker/security/traefik/traefik.yaml` |
| `media/video/jellyfin` | `docker/media/video/jellyfin/jellyfin.yaml` |

The container name is usually set explicitly in the compose file as `container_name:`. If not, Docker uses `<project>_<service>`.

## Docker Volume Paths

The base volume path is the `DOCKER_VOLUMES` environment variable, resolved at runtime:

**Typical path:** `/mnt/local/storage/docker-volumes/`

So a service's data volume is usually at:
```
/mnt/local/storage/docker-volumes/<service-name>/
```

Example: Open WebUI data is at `/mnt/local/storage/docker-volumes/open-webui/`.

## MCP Tools Available

These tools operate on services by `category/service-name`:

| Tool | What it does |
|---|---|
| `mcp__infra-mcp__container-service-config` | Show resolved docker-compose config |
| `mcp__infra-mcp__container-service-restart` | Restart containers |
| `mcp__infra-mcp__container-service-recreate` | Stop, remove, and re-create containers |
| `mcp__infra-mcp__container-service-up` | Start containers |
| `mcp__infra-mcp__container-service-down` | Stop containers |
| `mcp__infra-mcp__container-service-pull` | Pull latest image |
| `mcp__infra-mcp__list-container-tags` | List available image tags |
| `mcp__infra-mcp__get-most-specific-container-tag` | Resolve `latest` to a semver tag |

## Log Commands

Via labctl (preferred — handles env var substitution):
```bash
scripts/labctl.py service logs category/service-name
scripts/labctl.py service logs category/service-name --tail 200
scripts/labctl.py service logs category/service-name --follow
scripts/labctl.py service logs category/service-name --since 30m
scripts/labctl.py service logs category/service-name --timestamps
```

Direct docker (when you know the container name):
```bash
docker logs <container_name> --tail 100 2>&1
docker logs <container_name> --tail 200 2>&1 | grep -i "error\|exception\|fail"
```

## Applying a Fix

After changing a service YAML, apply with:
```bash
scripts/labctl.py service recreate category/service-name
```

Or via MCP:
```
mcp__infra-mcp__container-service-recreate(service_name="category/service-name")
```

## Environment Variable Loading Order

Variables are loaded in this precedence order (later overrides earlier):
1. `config/docker/.env` — common to all hosts
2. `config/docker/<hostname>/.env` — host-specific
3. `config/docker/.env.<service>` — service-specific (all hosts)
4. `config/docker/<hostname>/.env.<service>` — host + service specific

The `config/` directory is not in the repository (gitignored). `config-example/` contains templates.

## Reading Source Code of the Deployed Version

Get the image tag from the compose file (e.g. `ghcr.io/open-webui/open-webui:v0.9.5`), then use the GitHub API:

```bash
# Read a specific file at the deployed version tag
gh api repos/<org>/<repo>/contents/<path/to/file>?ref=<version-tag> \
  --jq '.content' | base64 -d

# Search for a string in a file
gh api repos/<org>/<repo>/contents/<path>?ref=<version-tag> \
  --jq '.content' | base64 -d | grep -i "SEARCH_TERM"

# List directory contents
gh api repos/<org>/<repo>/contents/<path>?ref=<version-tag> \
  --jq '.[].path'
```

## Common Service → GitHub Repo Mapping

| Service | GitHub repo |
|---|---|
| Open WebUI | `open-webui/open-webui` |
| LiteLLM | `BerriAI/litellm` |
| Traefik | `traefik/traefik` |
| Jellyfin | `jellyfin/jellyfin` |
| Authelia | `authelia/authelia` |
| Grafana | `grafana/grafana` |
| Prometheus | `prometheus/prometheus` |
| Ollama | `ollama/ollama` |
| Vaultwarden | `dani-garcia/vaultwarden` |
| Homepage | `gethomepage/homepage` |
| Navidrome | `navidrome/navidrome` |

## Proxy / Indirect Service Tip

Many errors are actually upstream of the failing service. Common indirect dependencies to check:

- **Traefik** — reverse proxy; check if routing/TLS is misconfigured
- **Authelia** — auth middleware; a 401/403 may be Authelia, not the app
- **Cloudflared** — tunnel; connectivity issues upstream
- **Ollama / LiteLLM** — AI backend; if an AI frontend errors, check the model provider first
