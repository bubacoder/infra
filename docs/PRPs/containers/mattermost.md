## Base information for Mattermost application

Application name: Mattermost
Homepage: https://mattermost.com
GitHub page: https://github.com/mattermost/docker
Install instructions URL: https://docs.mattermost.com/deployment-guide/server/deploy-containers.html
Category: communication
Dashboard Icon: mattermost.png
Dashboard Group: Connections
Short description: Secure collaboration platform for mission-critical work
Long description: Mattermost is a collaboration platform for mission-critical work that accelerates workflow by integrating people, processes, tools and AI infrastructure on a resilient and adaptable platform. The official Docker deployment solution provides enterprise-ready team messaging with extensive customization options.

## Container deployment

### Architecture Overview

The deployment consists of:
- **PostgreSQL database container** - Data persistence layer
- **Mattermost application container** - Core application server (Team or Enterprise edition)
- **NGINX reverse proxy container** (optional) - TLS termination and reverse proxy

### Docker Compose Configuration

The official deployment uses multiple compose files for different scenarios:

**Base configuration** (`docker-compose.yml`):
```yaml
services:
  postgres:
    image: postgres:${POSTGRES_IMAGE_TAG}
    restart: ${RESTART_POLICY}
    security_opt:
      - no-new-privileges:true
    pids_limit: 100
    read_only: true
    tmpfs:
      - /tmp
      - /var/run/postgresql
    volumes:
      - ${POSTGRES_DATA_PATH}:/var/lib/postgresql/data
    environment:
      - TZ
      - POSTGRES_USER
      - POSTGRES_PASSWORD
      - POSTGRES_DB

  mattermost:
    depends_on:
      - postgres
    image: mattermost/${MATTERMOST_IMAGE}:${MATTERMOST_IMAGE_TAG}
    restart: ${RESTART_POLICY}
    security_opt:
      - no-new-privileges:true
    pids_limit: 200
    read_only: ${MATTERMOST_CONTAINER_READONLY}
    tmpfs:
      - /tmp
    volumes:
      - ${MATTERMOST_CONFIG_PATH}:/mattermost/config:rw
      - ${MATTERMOST_DATA_PATH}:/mattermost/data:rw
      - ${MATTERMOST_LOGS_PATH}:/mattermost/logs:rw
      - ${MATTERMOST_PLUGINS_PATH}:/mattermost/plugins:rw
      - ${MATTERMOST_CLIENT_PLUGINS_PATH}:/mattermost/client/plugins:rw
      - ${MATTERMOST_BLEVE_INDEXES_PATH}:/mattermost/bleve-indexes:rw
    environment:
      - TZ
      - MM_SQLSETTINGS_DRIVERNAME
      - MM_SQLSETTINGS_DATASOURCE
      - MM_BLEVESETTINGS_INDEXDIR
      - MM_SERVICESETTINGS_SITEURL
```

**With NGINX reverse proxy** (`docker-compose.nginx.yml` overlay):
```yaml
services:
  nginx:
    depends_on:
      - mattermost
    container_name: nginx_mattermost
    image: nginx:${NGINX_IMAGE_TAG}
    restart: ${RESTART_POLICY}
    security_opt:
      - no-new-privileges:true
    pids_limit: 100
    read_only: true
    tmpfs:
      - /var/run
      - /var/cache
      - /var/log/nginx
    volumes:
      - ${NGINX_CONFIG_PATH}:/etc/nginx/conf.d:ro
      - ${NGINX_DHPARAMS_FILE}:/dhparams4096.pem
      - ${CERT_PATH}:/cert.pem:ro
      - ${KEY_PATH}:/key.pem:ro
      - shared-webroot:/usr/share/nginx/html
    environment:
      - TZ
    ports:
      - ${HTTPS_PORT}:443
      - ${HTTP_PORT}:80
  mattermost:
    ports:
      - ${CALLS_PORT}:${CALLS_PORT}/udp
      - ${CALLS_PORT}:${CALLS_PORT}/tcp

volumes:
  shared-webroot:
    name: shared-webroot

networks:
  default:
    name: mattermost
```

**Without NGINX** (`docker-compose.without-nginx.yml` overlay):
```yaml
services:
  mattermost:
    ports:
      - ${APP_PORT}:8065
      - ${CALLS_PORT}:${CALLS_PORT}/udp
      - ${CALLS_PORT}:${CALLS_PORT}/tcp
```

### Environment Variables

The deployment requires an `.env` file with the following key configuration:

#### Required Settings
- `DOMAIN` - Domain name for the service (e.g., `mm.example.com`)
- `TZ` - Timezone (e.g., `Europe/Berlin`, `UTC`)
- `RESTART_POLICY` - Container restart policy (default: `unless-stopped`)

#### PostgreSQL Configuration
- `POSTGRES_IMAGE_TAG` - PostgreSQL version (default: `14-alpine`)
- `POSTGRES_DATA_PATH` - Database volume path (default: `./volumes/db/var/lib/postgresql/data`)
- `POSTGRES_USER` - Database username (default: `mmuser`)
- `POSTGRES_PASSWORD` - Database password (should be changed from default)
- `POSTGRES_DB` - Database name (default: `mattermost`)

#### Mattermost Application
- `MATTERMOST_IMAGE` - Image variant: `mattermost-enterprise-edition` or `mattermost-team-edition`
- `MATTERMOST_IMAGE_TAG` - Version tag (e.g., `10.11.5`, `release-10.5`)
- `MATTERMOST_CONFIG_PATH` - Configuration volume path (default: `./volumes/app/mattermost/config`)
- `MATTERMOST_DATA_PATH` - Data volume path (default: `./volumes/app/mattermost/data`)
- `MATTERMOST_LOGS_PATH` - Logs volume path (default: `./volumes/app/mattermost/logs`)
- `MATTERMOST_PLUGINS_PATH` - Plugins volume path (default: `./volumes/app/mattermost/plugins`)
- `MATTERMOST_CLIENT_PLUGINS_PATH` - Client plugins path (default: `./volumes/app/mattermost/client/plugins`)
- `MATTERMOST_BLEVE_INDEXES_PATH` - Search index path (default: `./volumes/app/mattermost/bleve-indexes`)
- `MATTERMOST_CONTAINER_READONLY` - Make container readonly (default: `false`)
- `APP_PORT` - Application port when not using NGINX (default: `8065`)

#### Mattermost Configuration Variables
- `MM_SQLSETTINGS_DRIVERNAME` - Database driver (value: `postgres`)
- `MM_SQLSETTINGS_DATASOURCE` - Database connection string
- `MM_BLEVESETTINGS_INDEXDIR` - Bleve index directory (value: `/mattermost/bleve-indexes`)
- `MM_SERVICESETTINGS_SITEURL` - Site URL (e.g., `https://${DOMAIN}`)

#### NGINX Configuration (when using nginx overlay)
- `NGINX_IMAGE_TAG` - NGINX version (default: `alpine`, requires 1.25.1+)
- `NGINX_CONFIG_PATH` - NGINX config directory (default: `./nginx/conf.d`)
- `NGINX_DHPARAMS_FILE` - DH parameters file path (default: `./nginx/dhparams4096.pem`)
- `CERT_PATH` - TLS certificate path (default: `./volumes/web/cert/cert.pem`)
- `KEY_PATH` - TLS private key path (default: `./volumes/web/cert/key-no-password.pem`)
- `HTTPS_PORT` - HTTPS external port (default: `443`)
- `HTTP_PORT` - HTTP external port (default: `80`)
- `CALLS_PORT` - Mattermost Calls port for audio/video (default: `8443`)

### Deployment Steps

1. **Clone the official repository**:
   ```bash
   git clone https://github.com/mattermost/docker
   cd docker
   ```

2. **Create environment file**:
   ```bash
   cp env.example .env
   # Edit .env and set at minimum: DOMAIN, POSTGRES_PASSWORD
   ```

3. **Create required directories with proper permissions**:
   ```bash
   mkdir -p ./volumes/app/mattermost/{config,data,logs,plugins,client/plugins,bleve-indexes}
   sudo chown -R 2000:2000 ./volumes/app/mattermost
   ```

4. **Deploy without NGINX** (direct access on port 8065):
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.without-nginx.yml up -d
   ```
   Access via: `http://<YOUR_MM_DOMAIN>:8065/`

5. **Deploy with NGINX** (with TLS termination):
   ```bash
   # Ensure certificates and NGINX config are in place first
   docker compose -f docker-compose.yml -f docker-compose.nginx.yml up -d
   ```
   Access via: `https://<YOUR_MM_DOMAIN>/`

### Version Management

- Use specific version tags (e.g., `10.11.5`, `release-10.5`) in production
- Avoid generic rolling tags like `latest` or `release-x` for stability
- The `MATTERMOST_IMAGE_TAG` variable in `.env` controls the deployed version
- Choose between Enterprise Edition (`mattermost-enterprise-edition`) or Team Edition (`mattermost-team-edition`)

### Security Considerations

1. **Container Security**:
   - Containers run with `no-new-privileges` security option
   - Read-only root filesystem where possible
   - Limited process IDs (pids_limit)
   - Temporary filesystems for runtime data

2. **Database Security**:
   - Change default `POSTGRES_PASSWORD` from example values
   - Consider creating a non-superuser database user (see `docs/creation-of-nonsuperuser.md` in repo)
   - Database connection uses internal Docker network (not exposed externally)

3. **Network Security**:
   - When using NGINX, only ports 443, 80, and 8443 are exposed
   - Without NGINX, only port 8065 and 8443 are exposed
   - Use proper TLS certificates (not self-signed in production)

4. **File Permissions**:
   - Mattermost container runs as UID/GID 2000
   - NGINX container runs as UID/GID 101
   - Ensure volume directories have correct ownership

5. **SSO Integration**:
   - For GitLab SSO, mount the PKI chain: `${GITLAB_PKI_CHAIN_PATH}:/etc/ssl/certs/pki_chain.pem:ro`
   - Prevents "certificate signed by unknown authority" errors

### Additional Configuration

1. **Environment Variable Precedence**:
   - Variables set in `.env` override settings in `config.json`
   - Settings configured via environment variables are greyed out in System Console
   - Full documentation: https://docs.mattermost.com/administration/config-settings.html

2. **Persistent Data**:
   - All data stored in `./volumes/` directory structure
   - Backup these directories for disaster recovery
   - Database at `./volumes/db/`
   - Application data at `./volumes/app/mattermost/`

3. **Mattermost Calls**:
   - Requires port 8443 (both TCP and UDP) for audio/video functionality
   - Configured via `CALLS_PORT` environment variable

### Possible Improvements

1. **Automated Updates**:
   - Consider Watchtower for automatic image updates (commented out in compose file)
   - Note: Granting Watchtower access to Docker socket is a security consideration

2. **Let's Encrypt Integration**:
   - Use shared webroot volume for certificate renewal
   - Configure certbot/acme client to use `shared-webroot` volume

3. **High Availability**:
   - Deploy multiple Mattermost application containers behind load balancer
   - Use external PostgreSQL cluster instead of containerized database
   - Consider S3-compatible storage for file uploads

4. **Monitoring**:
   - Integrate with Prometheus for metrics collection
   - Configure log aggregation for centralized logging
   - Set up health checks and alerting

5. **Backup Strategy**:
   - Automate PostgreSQL database backups
   - Backup Mattermost data directory regularly
   - Test restore procedures periodically

6. **External Reverse Proxy**:
   - Instead of bundled NGINX, use existing reverse proxy (Traefik, Caddy, etc.)
   - Deploy with `docker-compose.without-nginx.yml` and proxy to port 8065
   - Simplifies certificate management and multi-service routing
