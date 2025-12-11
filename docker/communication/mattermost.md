# Mattermost Deployment Guide

Mattermost is a secure collaboration platform for mission-critical work that provides enterprise-ready team messaging with extensive customization options.

## Prerequisites

Before deploying Mattermost, ensure the following services are running:

1. **PostgreSQL** - Database backend (deployed via `docker/database/postgresql.yaml`)
2. **Traefik** - Reverse proxy for HTTPS access
3. **Authelia** - SSO authentication (configured via `localaccess-sso` middleware)

## Database Setup

Mattermost requires its own database within the PostgreSQL instance. Create the database and user before starting Mattermost:

### Step 1: Access PostgreSQL Container

```bash
docker exec -it postgresql psql -U postgres
```

### Step 2: Create Mattermost Database and User

```sql
-- Create the Mattermost user
CREATE USER mattermost WITH PASSWORD 'your-secure-password-here';

-- Create the Mattermost database
CREATE DATABASE mattermost WITH OWNER mattermost;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE mattermost TO mattermost;

-- Exit psql
\q
```

## Environment Configuration

Add the following variables to your `config/docker/<hostname>/.env` file:

```bash
### Mattermost configuration
MATTERMOST_POSTGRES_USER="mattermost"
MATTERMOST_POSTGRES_PASSWORD="your-secure-password-here"
MATTERMOST_POSTGRES_DB="mattermost"
```

**Important**: Use the same password you set when creating the PostgreSQL user.

## Deployment

Deploy Mattermost using the standard workflow:

```bash
# Deploy the service
task docker:apply

# Or use labctl.py directly
scripts/labctl.py service up communication/mattermost
```

## Initial Setup

1. Access Mattermost at: `https://mattermost.${MYDOMAIN}/`
2. Create the first admin account during initial setup
3. Configure team settings and channels as needed

## Configuration

### File Permissions

Mattermost container runs as UID/GID 2000. If you encounter permission issues:

```bash
sudo chown -R 2000:2000 ${DOCKER_VOLUMES}/mattermost
```

### Site URL

The site URL is automatically configured via the `MM_SERVICESETTINGS_SITEURL` environment variable to match your domain.

### SMTP Configuration

To enable email notifications, add the following environment variables to the compose file:

```yaml
environment:
  MM_EMAILSETTINGS_ENABLESMTPAUTH: true
  MM_EMAILSETTINGS_SMTPUSERNAME: your-smtp-username
  MM_EMAILSETTINGS_SMTPPASSWORD: your-smtp-password
  MM_EMAILSETTINGS_SMTPSERVER: smtp.example.com
  MM_EMAILSETTINGS_SMTPPORT: 587
  MM_EMAILSETTINGS_FEEDBACKEMAIL: noreply@example.com
```

### S3 Storage (MinIO Integration)

To use MinIO for file uploads instead of local storage:

```yaml
environment:
  MM_FILESETTINGS_DRIVERNAME: amazons3
  MM_FILESETTINGS_AMAZONS3ACCESSKEYID: minio-access-key
  MM_FILESETTINGS_AMAZONS3SECRETACCESSKEY: minio-secret-key
  MM_FILESETTINGS_AMAZONS3BUCKET: mattermost
  MM_FILESETTINGS_AMAZONS3ENDPOINT: minio.${MYDOMAIN}
  MM_FILESETTINGS_AMAZONS3SSL: true
```

### GitLab SSO

To enable GitLab SSO integration, mount the PKI chain and configure OAuth settings:

```yaml
volumes:
  - /path/to/gitlab-pki-chain.pem:/etc/ssl/certs/pki_chain.pem:ro
```

Then configure GitLab OAuth in Mattermost System Console.

## Monitoring

### Health Check

Check if Mattermost is running:

```bash
docker ps | grep mattermost
```

### View Logs

```bash
scripts/labctl.py service logs communication/mattermost
```

### Prometheus Metrics

Mattermost exposes metrics at `/metrics` endpoint. Add to your Prometheus configuration:

```yaml
- job_name: 'mattermost'
  static_configs:
    - targets: ['mattermost:8067']
```

## Backup

Back up the following:

1. **Database**: Use `pg_dump` for PostgreSQL backup
2. **Data directory**: `${DOCKER_VOLUMES}/mattermost/data`
3. **Config directory**: `${DOCKER_VOLUMES}/mattermost/config`
4. **Plugins**: `${DOCKER_VOLUMES}/mattermost/plugins`

Example backup script:

```bash
# Backup database
docker exec postgresql pg_dump -U mattermost mattermost > mattermost-db-backup.sql

# Backup data directories
tar -czf mattermost-data-backup.tar.gz ${DOCKER_VOLUMES}/mattermost/
```

## Troubleshooting

### Connection Refused to PostgreSQL

- Ensure PostgreSQL service is running: `docker ps | grep postgresql`
- Check if database exists: `docker exec -it postgresql psql -U postgres -l`
- Verify environment variables in `.env` file

### Permission Denied Errors

```bash
sudo chown -R 2000:2000 ${DOCKER_VOLUMES}/mattermost
```

### Cannot Access via Browser

- Check Traefik logs: `docker logs traefik`
- Verify DNS resolution: `nslookup mattermost.${MYDOMAIN}`
- Check if service is in proxy network: `docker network inspect proxy`

## Upgrading

To upgrade Mattermost:

1. Check release notes: https://docs.mattermost.com/about/mattermost-release-notes.html
2. Update image tag in `docker/communication/mattermost.yaml`
3. Pull new image and recreate container:

```bash
scripts/labctl.py service pull communication/mattermost
scripts/labctl.py service recreate communication/mattermost
```

## Resources

- Official Documentation: https://docs.mattermost.com/
- Docker Deployment Guide: https://docs.mattermost.com/deployment-guide/server/deploy-containers.html
- GitHub Repository: https://github.com/mattermost/docker
- Community Forum: https://forum.mattermost.com/
