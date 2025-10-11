## Base information for Microsoft SQL Server 2025 application

Application name: Microsoft SQL Server 2025
Homepage: https://www.microsoft.com/en-us/sql-server
GitHub page: N/A (proprietary software)
Install instructions URL: https://raw.githubusercontent.com/MicrosoftDocs/sql-docs/refs/heads/live/docs/linux/quickstart-install-connect-docker.md
Container image(s): mcr.microsoft.com/mssql/server:2025-latest
Category: storage
Dashboard Icon: microsoft-sql-server.png
Dashboard Group: Storage
Short description: AI-ready enterprise relational database with best-in-class performance and security
Long description: Microsoft SQL Server is an enterprise-grade relational database management system (RDBMS) with comprehensive data management, business intelligence, and analytics capabilities. SQL Server 2025 is an AI-ready database offering best-in-class security, performance, and availability from ground to cloud.

## Container deployment

### Docker Run Command

Basic deployment using docker run:

```bash
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=<YourStrong@Passw0rd>" \
   -p 1433:1433 --name sql1 --hostname sql1 \
   -d \
   mcr.microsoft.com/mssql/server:2025-latest
```

### Environment Variables

Required environment variables:

- **ACCEPT_EULA**: Must be set to `Y` to confirm acceptance of the End-User License Agreement
- **MSSQL_SA_PASSWORD**: Sets the system administrator (SA) password. Must meet SQL Server password complexity requirements:
  - At least 8 characters
  - Contains characters from three of the following categories:
    - Uppercase letters (A-Z)
    - Lowercase letters (a-z)
    - Numbers (0-9)
    - Non-alphanumeric symbols (e.g., !, $, #, %)

Optional environment variables:

- **MSSQL_COLLATION**: Custom SQL Server collation (default is SQL_Latin1_General_CP1_CI_AS)
- **MSSQL_PID**: SQL Server edition or product key (default is Developer edition)

### Port Mappings

- **1433**: SQL Server default TCP port for client connections (host:container mapping should be 1433:1433)

### Volume Mounts

For data persistence, it's recommended to mount volumes for:

- **/var/opt/mssql/data**: Database files
- **/var/opt/mssql/log**: Transaction log files
- **/var/opt/mssql/secrets**: Certificates and keys

Example with volumes:

```bash
docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=<YourStrong@Passw0rd>" \
   -p 1433:1433 --name sql1 --hostname sql1 \
   -v sqldata:/var/opt/mssql/data \
   -v sqllog:/var/opt/mssql/log \
   -v sqlsecrets:/var/opt/mssql/secrets \
   -d \
   mcr.microsoft.com/mssql/server:2025-latest
```

### Security Considerations

1. **Strong Passwords**: Always use strong passwords that meet SQL Server complexity requirements
2. **Change Default SA Password**: The SA account is a well-known privileged account - change the password immediately after deployment
3. **Disable SA Account**: In production environments, it's recommended to disable the SA account and use Windows Authentication or create separate user accounts with appropriate permissions
4. **Network Security**: Consider limiting network access to the SQL Server port (1433) using firewall rules or Docker network configurations
5. **Regular Updates**: Keep the container image updated to receive security patches and bug fixes
6. **Least Privilege**: Run containers with minimal necessary privileges

### Connectivity

#### Internal Connection (within container):

```bash
docker exec -it sql1 /opt/mssql-tools/bin/sqlcmd \
   -S localhost -U SA -P "<YourStrong@Passw0rd>"
```

#### External Connection:

Connect using the host IP address and port 1433 with various tools:
- SQL Server Management Studio (SSMS)
- Azure Data Studio
- Visual Studio Code with mssql extension
- sqlcmd command-line tool

### Container Management

Stop the container:
```bash
docker stop sql1
```

Remove the container:
```bash
docker rm sql1
```

Note: Removing the container without volume mounts will result in data loss. Always use named volumes or bind mounts for production deployments.

### Docker Compose Example

```yaml
services:
  mssql:
    image: mcr.microsoft.com/mssql/server:2025-latest
    container_name: mssql-server
    hostname: mssql
    environment:
      - ACCEPT_EULA=Y
      - MSSQL_SA_PASSWORD=${MSSQL_SA_PASSWORD}
      - MSSQL_PID=Developer
    ports:
      - "1433:1433"
    volumes:
      - mssql_data:/var/opt/mssql/data
      - mssql_log:/var/opt/mssql/log
      - mssql_secrets:/var/opt/mssql/secrets
    restart: unless-stopped

volumes:
  mssql_data:
  mssql_log:
  mssql_secrets:
```

### Available Versions

Microsoft provides SQL Server container images for multiple versions:
- SQL Server 2017
- SQL Server 2019
- SQL Server 2022
- SQL Server 2025 (Preview)

All versions are based on Ubuntu Linux and available from the Microsoft Container Registry (MCR).

### Further Improvements

1. **Health Checks**: Implement Docker health checks to monitor SQL Server availability
2. **Resource Limits**: Set CPU and memory limits appropriate for your workload
3. **Backup Strategy**: Implement automated backup solutions using mounted volumes
4. **Monitoring**: Integrate with monitoring solutions (Prometheus, Grafana) for performance metrics
5. **High Availability**: Consider SQL Server Always On Availability Groups for production environments
6. **Read-Only Replicas**: Deploy read-only replicas for load distribution
7. **Custom Configuration**: Mount custom mssql.conf for advanced SQL Server configuration
