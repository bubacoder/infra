## Base information for Obsidian application

Application name: Obsidian
Homepage: https://obsidian.md
GitHub page: https://github.com/obsidianmd
Install instructions URL: https://docs.linuxserver.io/images/docker-obsidian/
Container image(s): lscr.io/linuxserver/obsidian:latest
Category: tools
Dashboard Icon: obsidian.png
Dashboard Group: Tools
Short description: A powerful knowledge base that works on top of a local folder of plain text Markdown files
Long description: Obsidian is a free and flexible app for your private thoughts that stores notes locally with extensive plugin support and open file formats. It provides a powerful knowledge management system with linking, graph view, and customizable workspace features.

## Container deployment

### Docker Compose Configuration

```yaml
services:
  obsidian:
    image: lscr.io/linuxserver/obsidian:latest
    container_name: obsidian
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Etc/UTC
    volumes:
      - /path/to/config:/config
    ports:
      - 3000:3000
      - 3001:3001
    shm_size: "1gb"
    restart: unless-stopped
```

### Environment Variables

- `PUID`: User ID for file permissions (default: 1000)
- `PGID`: Group ID for file permissions (default: 1000)
- `TZ`: Timezone setting (default: Etc/UTC)
- `CUSTOM_USER` (optional): Username for basic HTTP authentication
- `PASSWORD` (optional): Password for basic HTTP authentication
- `LC_ALL` (optional): Locale setting for internationalization

### Port Configuration

- **Port 3000**: HTTP desktop GUI interface (must be proxied for external access)
- **Port 3001**: HTTPS desktop GUI interface

### Volume Mounts

- `/config`: User home directory that stores program settings, vault files, and Obsidian configuration

### Security Considerations

**Important Security Warning**: This container provides privileged access to the host system.

- **No built-in authentication**: By default, the container has no authentication mechanism
- **HTTPS requirement**: Full functionality requires HTTPS access
- **Basic authentication**: Optional via `CUSTOM_USER` and `PASSWORD` environment variables
- **Reverse proxy recommended**: Should be placed behind a reverse proxy (like Traefik) when exposed to the internet
- **Network security**: Consider restricting access to trusted networks only

### Additional Features

- **GPU acceleration**: Supports hardware acceleration when properly configured
- **Shared memory**: Configured with 1GB shared memory (`shm_size: "1gb"`) for optimal performance
- **Docker-in-Docker**: Optional privileged mode available if needed for advanced use cases

### Deployment Recommendations

1. Use a reverse proxy with proper SSL/TLS termination
2. Implement additional authentication layer (e.g., Authelia) for internet exposure
3. Regular backups of the `/config` volume containing vault data
4. Consider setting appropriate user permissions (PUID/PGID) to match host user
5. Monitor resource usage as Obsidian can be resource-intensive with large vaults
