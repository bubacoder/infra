## Base information for Gitea application

Application name: Gitea
Homepage: https://about.gitea.com/
GitHub page: https://github.com/go-gitea/gitea
Install instructions URL: https://docs.gitea.com/installation/install-with-docker
Container image(s): gitea/gitea:1.24.6
Category: dev
Dashboard Icon: gitea.png
Dashboard Group: Development
Short description: Self-hosted Git service
Long description: Gitea is a lightweight, open-source self-hosted Git service. It's a painless, community-managed fork of Gogs with enhanced features focused on Git management and CI/CD integration.

## Container deployment

### Docker Compose Configuration

Below is a Docker Compose configuration for deploying Gitea with SQLite (simplest setup):

```yaml
version: "3"

networks:
  gitea:
    external: false

services:
  server:
    image: gitea/gitea:1.24.6
    container_name: gitea
    environment:
      - USER_UID=1000
      - USER_GID=1000
      # Use the following format to override settings in app.ini
      # - GITEA__section_name__KEY_NAME=value
    restart: always
    networks:
      - gitea
    volumes:
      - ./gitea:/data
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro
    ports:
      - "3000:3000"
      - "222:22"  # Map SSH port to avoid conflicts with host SSH
```

### PostgreSQL Configuration

For improved performance, PostgreSQL is recommended:

```yaml
version: "3"

networks:
  gitea:
    external: false

services:
  server:
    image: gitea/gitea:1.24.6
    container_name: gitea
    environment:
      - USER_UID=1000
      - USER_GID=1000
      - GITEA__database__DB_TYPE=postgres
      - GITEA__database__HOST=db:5432
      - GITEA__database__NAME=gitea
      - GITEA__database__USER=gitea
      - GITEA__database__PASSWD=gitea_password
    restart: always
    networks:
      - gitea
    volumes:
      - ./gitea:/data
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro
    ports:
      - "3000:3000"
      - "222:22"
    depends_on:
      - db

  db:
    image: postgres:15
    restart: always
    environment:
      - POSTGRES_USER=gitea
      - POSTGRES_PASSWORD=gitea_password
      - POSTGRES_DB=gitea
    networks:
      - gitea
    volumes:
      - ./postgres:/var/lib/postgresql/data
```

### Security Considerations

1. **Secret Key**: Generate a unique secret key:
   ```bash
   docker run -it --rm gitea/gitea:1.24.6 gitea generate secret SECRET_KEY
   ```
   Then set it in your environment:
   ```yaml
   environment:
     - GITEA__security__SECRET_KEY=your_generated_secret
   ```

2. **HTTPS**: Configure Gitea behind a reverse proxy for HTTPS:
   ```yaml
   environment:
     - GITEA__server__ROOT_URL=https://git.yourdomain.com/
     - GITEA__server__DOMAIN=git.yourdomain.com
   ```

3. **SSH Access**: If Git SSH access is required, ensure the SSH port is exposed and configured correctly:
   ```yaml
   environment:
     - GITEA__server__SSH_DOMAIN=git.yourdomain.com
     - GITEA__server__SSH_PORT=222
     - GITEA__server__SSH_LISTEN_PORT=22
   ```

### Important Environment Variables

- `USER_UID`/`USER_GID`: User/group ID for file ownership (default 1000)
- `GITEA__server__DOMAIN`: Domain name of your Gitea instance
- `GITEA__server__ROOT_URL`: Full URL to access your Gitea instance
- `GITEA__database__DB_TYPE`: Database type (mysql, postgres, mssql, sqlite3)
- `GITEA__security__SECRET_KEY`: Secret for JWT and session encryption
- `GITEA__security__INTERNAL_TOKEN`: Internal API token (generate with the command above)
- `GITEA__server__DISABLE_SSH`: Set to true to disable SSH functionality

### Volume Management

Key directories in the `/data` volume:
- `/data/gitea`: Application data
- `/data/git`: Git repositories
- `/data/ssh`: SSH keys and configuration
- `/data/lfs`: Git LFS objects

### Post-Installation Setup

After deployment, visit `http://your-server:3000/` to complete the setup:
1. Configure your database settings if not using environment variables
2. Set the site title and other application settings
3. Create the initial admin account

### Upgrading

1. Update the image version in your docker-compose.yml
2. Pull the new image: `docker-compose pull`
3. Restart the container: `docker-compose up -d`
4. Check logs for any errors: `docker-compose logs -f`

It's recommended to back up your data before upgrading:
```bash
cp -r ./gitea ./gitea_backup_$(date +%Y%m%d)
```
