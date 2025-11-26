## Base information for Adminer application

Application name: Adminer
Homepage: https://www.adminer.org
GitHub page: https://github.com/vrana/adminer
Install instructions URL: https://hub.docker.com/_/adminer/
Category: storage
Dashboard Icon: adminer.png
Dashboard Group: Storage
Short description: Full-featured database management tool in a single PHP file
Long description: Adminer is a full-featured database management tool written in PHP that consists of a single file ready to deploy to the target server. It supports MySQL, MariaDB, PostgreSQL, CockroachDB, SQLite, MS SQL, Oracle, and through plugins: Elasticsearch, SimpleDB, MongoDB, Firebird, ClickHouse, and IMAP systems. Adminer offers a tidier user interface, better support for database features, higher performance and more security compared to phpMyAdmin.

## Container deployment

### Docker Compose Configuration

Basic deployment example:

```yaml
services:
  adminer:
    image: adminer
    restart: always
    ports:
      - 8080:8080
```

Example with database:

```yaml
services:
  adminer:
    image: adminer
    restart: always
    ports:
      - 8080:8080

  db:
    image: mysql:5.6
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: example
```

### Docker Run Command

Standalone mode with database link:
```bash
docker run --link some_database:db -p 8080:8080 adminer
```

Access the interface at `http://localhost:8080` or `http://host-ip:8080`.

### FastCGI Variant

For FastCGI-capable web servers:
```bash
docker run --link some_database:db -p 9000:9000 adminer:fastcgi
```

**Security Note:** The FastCGI socket exposes to port 9000. Implement firewall rules or use private Docker networks to prevent unauthorized access.

### Environment Variables

**ADMINER_PLUGINS:** Load official plugins by passing a space-separated filename list.

Example:
```yaml
environment:
  ADMINER_PLUGINS: 'tables-filter tinymce'
```

**Plugin Configuration:** Some plugins require parameters and need custom configuration files mounted in `/var/www/html/plugins-enabled/`.

Available plugins: https://github.com/vrana/adminer/tree/master/plugins

### Security Considerations

1. **Access Control:** Adminer provides direct database access, so it should be placed behind authentication (e.g., Traefik with Authelia)
2. **Network Isolation:** Use private Docker networks instead of exposing ports publicly
3. **Database Credentials:** Never hardcode credentials in compose files; use environment variables or Docker secrets
4. **FastCGI Exposure:** When using the FastCGI variant, ensure port 9000 is not exposed to untrusted networks
5. **Regular Updates:** Keep the Adminer image updated for security patches

### Supported Architectures

The official image supports: amd64, arm32v6, arm32v7, arm64v8, i386, ppc64le, riscv64, and s390x.

### Database Support

Adminer can manage the following database systems:
- MySQL / MariaDB
- PostgreSQL / CockroachDB
- SQLite
- MS SQL
- Oracle
- Firebird
- SimpleDB (via plugins)
- Elasticsearch (via plugins)
- MongoDB (via plugins)

### Recommended Improvements

1. **Reverse Proxy Integration:** Deploy behind Traefik with authentication middleware
2. **Custom Plugins:** Mount custom plugin configuration for enhanced functionality
3. **Theme Customization:** Adminer supports custom CSS themes that can be mounted
4. **Database Network:** Create a dedicated Docker network for database connections
5. **Read-Only Mode:** For production databases, consider using database user accounts with read-only permissions

### Example Production-Ready Deployment

```yaml
services:
  adminer:
    image: adminer
    container_name: adminer
    restart: unless-stopped
    networks:
      - database_network
      - proxy_network
    environment:
      ADMINER_PLUGINS: 'tables-filter tinymce'
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.adminer.rule=Host(`adminer.example.com`)"
      - "traefik.http.routers.adminer.entrypoints=websecure"
      - "traefik.http.routers.adminer.tls.certresolver=letsencrypt"
      - "traefik.http.routers.adminer.middlewares=authelia@docker"

networks:
  database_network:
    external: true
  proxy_network:
    external: true
```
