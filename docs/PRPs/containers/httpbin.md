## Base information for httpbin application

Application name: httpbin (go-httpbin)
Homepage: https://httpbin.org/
GitHub page: https://github.com/mccutchen/go-httpbin
Install instructions URL: https://github.com/mccutchen/go-httpbin
Category: tools
Dashboard Icon: https://httpbin.org/static/favicon.ico
Dashboard Group: Development
Short description: A simple HTTP request & response testing service for developers
Long description: go-httpbin is an actively maintained Go rewrite of the classic httpbin service, offering the same HTTP Request & Response API with lower resource usage, versioned releases, and multi-arch Docker images. It allows developers to test HTTP clients, inspect request details, and simulate various HTTP responses — covering methods, status codes, headers, auth, redirects, delays, and more.

## Container deployment

### Docker Image

- **Image:** `ghcr.io/mccutchen/go-httpbin:2.21.0`
- **GitHub Container Registry:** `ghcr.io/mccutchen/go-httpbin`
- **Docker Hub mirror:** `mccutchen/go-httpbin`
- **Architectures:** `linux/amd64`, `linux/arm64`

### Quick Start (docker run)

```bash
docker run -P ghcr.io/mccutchen/go-httpbin
```

### Docker Compose

```yaml
name: httpbin
services:
  httpbin:
    image: ghcr.io/mccutchen/go-httpbin:2.21.0
    container_name: httpbin
    restart: unless-stopped
    networks:
      - proxy
    labels:
      traefik.enable: true
      traefik.http.routers.httpbin.middlewares: localaccess@file
      traefik.http.services.httpbin.loadbalancer.server.port: 8080
      homepage.group: Development
      homepage.name: Httpbin
      homepage.icon: https://httpbin.org/static/favicon.ico
      homepage.href: https://httpbin.${MYDOMAIN}/
      homepage.description: HTTP request & response testing service

networks:
  proxy:
    external: true
```

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `HOST` | Listening address | `0.0.0.0` |
| `PORT` | Listening port | `8080` |
| `MAX_BODY_SIZE` | Max request/response body size in bytes | `1048576` (1 MiB) |
| `MAX_DURATION` | Maximum simulated response duration | `10s` |
| `ALLOWED_REDIRECT_DOMAINS` | Comma-separated list of allowed redirect targets | (unrestricted) |
| `EXCLUDE_HEADERS` | Headers to strip from echoed responses | (none) |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

No environment variables are required for basic operation.

### Endpoints Overview

| Endpoint | Description |
|---|---|
| `/get`, `/post`, `/put`, `/delete`, ... | Echoes the full request for the given HTTP method |
| `/status/{codes}` | Returns a response with the specified HTTP status code |
| `/headers` | Returns the request headers as received |
| `/ip` | Returns the requester's IP address |
| `/delay/{n}` | Delays the response by n seconds (capped by `MAX_DURATION`) |
| `/redirect/{n}` | Performs n consecutive redirects |
| `/basic-auth/{user}/{pass}` | Tests HTTP Basic Authentication |
| `/anything` | Returns everything passed in the request |

### Security Considerations

- **Local access only:** The `localaccess@file` Traefik middleware restricts access to the local network. Do not expose httpbin publicly — it can be abused for SSRF probing, open-redirect chains, or leaking internal header details.
- **No built-in authentication:** httpbin has no login system. Add `authelia@file` to the Traefik middleware chain if broader authentication is needed.
- **Sensitive data echoed back:** All request data (headers, body, query params) is reflected in responses — avoid routing requests containing real credentials through httpbin.
- **Redirect restriction:** Set `ALLOWED_REDIRECT_DOMAINS` to limit which domains the `/redirect-to` endpoint can target, reducing open-redirect risk.
- **Non-root image:** Since v2.19.0 the image runs as a non-root user, which is good practice. Port 8080 avoids any privileged-port concerns.
