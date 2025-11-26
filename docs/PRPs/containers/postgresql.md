## Base information for PostgreSQL application

Application name: PostgreSQL
Homepage: https://www.postgresql.org/
GitHub page: https://github.com/docker-library/postgres (Docker official image repository)
Install instructions URL: https://hub.docker.com/_/postgres
Category: storage
Dashboard Icon: postgresql.png
Dashboard Group: Storage
Short description: Powerful open source object-relational database system
Long description: PostgreSQL is a powerful, open source object-relational database system with over 35 years of active development that has earned it a strong reputation for reliability, feature robustness, and performance. It is positioned as "The world's most advanced open source database".

## Container deployment

### Docker Compose Example

The official documentation provides this basic example with Adminer as a database management interface:

```yaml
services:
  db:
    image: postgres
    restart: always
    shm_size: 128mb
    environment:
      POSTGRES_PASSWORD: example

  adminer:
    image: adminer
    restart: always
    ports:
      - 8080:8080
```

**Important**: Set `shm_size: 128mb` to optimize performance and avoid shared memory issues.

### Docker Run Command

Basic startup command:
```bash
docker run --name some-postgres -e POSTGRES_PASSWORD=mysecretpassword -d postgres
```

### Essential Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `POSTGRES_PASSWORD` | **Yes** | Sets superuser password; must not be empty |
| `POSTGRES_USER` | No | Creates named superuser (defaults to `postgres`) |
| `POSTGRES_DB` | No | Specifies initial database name |
| `POSTGRES_INITDB_ARGS` | No | Passes arguments to `initdb` (e.g., `--data-checksums`) |
| `POSTGRES_INITDB_WALDIR` | No | Designates transaction log directory |
| `POSTGRES_HOST_AUTH_METHOD` | No | Controls authentication method (default: `scram-sha-256`) |
| `PGDATA` | No | PostgreSQL 18+: `/var/lib/postgresql/18/docker` |

### Volume Configuration

**Critical for data persistence:**

- **PostgreSQL 17 and below**: Mount volumes at `/var/lib/postgresql/data` (not at `/var/lib/postgresql`)
- **PostgreSQL 18+**: Mount at `/var/lib/postgresql`

The documentation emphasizes: "Mount the data volume at `/var/lib/postgresql/data` and not at `/var/lib/postgresql` because mounts at the latter path will not persist database data when the container is re-created."

Example with named volume:
```yaml
services:
  db:
    image: postgres:17
    volumes:
      - postgres-data:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD: example

volumes:
  postgres-data:
```

### Docker Secrets Support

For secure password handling in production:

```bash
docker run --name some-postgres \
  -e POSTGRES_PASSWORD_FILE=/run/secrets/postgres-passwd \
  -d postgres
```

Supported variables with `_FILE` suffix:
- `POSTGRES_PASSWORD_FILE`
- `POSTGRES_USER_FILE`
- `POSTGRES_DB_FILE`
- `POSTGRES_INITDB_ARGS_FILE`

### Initialization Scripts

PostgreSQL supports automatic database initialization through scripts placed in `/docker-entrypoint-initdb.d/`:

- `*.sql` files execute as the PostgreSQL superuser
- `*.sh` executable scripts run with superuser privileges
- Non-executable `*.sh` scripts are sourced

**Important limitation**: Scripts only run if you start the container with an empty data directory.

Example initialization script:
```bash
#!/usr/bin/env bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" <<-EOSQL
  CREATE USER docker;
  CREATE DATABASE docker;
  GRANT ALL PRIVILEGES ON DATABASE docker TO docker;
EOSQL
```

### Database Configuration

#### Via Configuration File

```bash
docker run -d --name some-postgres \
  -v "$PWD/my-postgres.conf":/etc/postgresql/postgresql.conf \
  -e POSTGRES_PASSWORD=mysecretpassword \
  postgres -c 'config_file=/etc/postgresql/postgresql.conf'
```

#### Via Command-Line Arguments

```bash
docker run -d --name some-postgres \
  -e POSTGRES_PASSWORD=mysecretpassword \
  postgres -c shared_buffers=256MB -c max_connections=200
```

In Docker Compose:
```yaml
services:
  db:
    image: postgres
    command: -c shared_buffers=256MB -c max_connections=200
    environment:
      POSTGRES_PASSWORD: example
```

**Essential for network access**: You must set `listen_addresses = '*'` so that other containers can access PostgreSQL.

### Networking

To connect from another container using psql:

```bash
docker run -it --rm --network some-network postgres \
  psql -h some-postgres -U postgres
```

The system uses Unix socket connections internally for initialization scripts.

### Security Considerations

1. **Authentication**:
   - Local connections use `trust` authentication (no password required from localhost)
   - Remote connections require password authentication
   - **Not recommended**: Using `trust` for all connections, as it allows anyone to connect without a password

2. **Password Management**:
   - Always set `POSTGRES_PASSWORD` (required)
   - Use Docker Secrets for production deployments
   - Never commit passwords to version control

3. **Network Exposure**:
   - Don't expose PostgreSQL port (5432) to the public internet without proper firewall rules
   - Use reverse proxy or VPN for remote access
   - Consider using connection pooling (e.g., PgBouncer) for better resource management

4. **Data Protection**:
   - Enable data checksums with `POSTGRES_INITDB_ARGS=--data-checksums`
   - Use named volumes for data persistence
   - Implement regular backup strategies

### Supported Versions

Current stable releases:
- PostgreSQL 18.1 (latest)
- PostgreSQL 17.7
- PostgreSQL 16.11
- PostgreSQL 15.15
- PostgreSQL 14.20

Available as:
- Standard Debian-based images
- Alpine variants (smaller size)
- Version-specific base OS tags (Trixie, Bookworm, Alpine 3.21/3.22)

### Best Practices

1. **Data Persistence**: Always use named volumes instead of anonymous volumes
2. **Initialization Timing**: Account for database initialization delay on first startup
3. **Password Management**: Use Docker Secrets for production deployments
4. **Locale Support**: Alpine 15+ supports ICU locales via `POSTGRES_INITDB_ARGS`
5. **Script Safety**: Include `set -e` in shell scripts; use `ON_ERROR_STOP=1` in SQL scripts
6. **Health Checks**: Implement health checks to ensure database availability
7. **Resource Limits**: Set appropriate `shm_size` (at least 128MB recommended)

### Example Health Check

```yaml
services:
  db:
    image: postgres:17
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    environment:
      POSTGRES_PASSWORD: example
```

### Possible Improvements

1. **Connection Pooling**: Add PgBouncer container for better connection management
2. **Backup Solution**: Implement automated backups using pg_dump or continuous archiving (WAL-E, pgBackRest)
3. **Monitoring**: Add PostgreSQL exporter for Prometheus monitoring
4. **Replication**: Set up streaming replication for high availability
5. **Performance Tuning**: Optimize postgresql.conf settings based on workload
6. **SSL/TLS**: Enable encrypted connections for security
7. **Extension Management**: Pre-install commonly used extensions (PostGIS, pg_stat_statements, etc.)
8. **Log Management**: Configure log collection and rotation
