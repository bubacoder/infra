# Docker Service Network Isolation

This document describes the network isolation approach used in this infrastructure setup to improve security by limiting container-to-container communication.

## Network Architecture

### Overview

The infrastructure uses a multi-tier network architecture to isolate services:

1. **Service-Specific Proxy Networks** - Dedicated proxy networks for sensitive services (e.g., `vaultwarden-proxy`)
2. **Category-Based Proxy Networks** - Shared networks for groups of related services (e.g., `storage-proxy`)
3. **Service-Specific Backend Networks** - Private networks for service components (e.g., `vaultwarden-backend`)
4. **Legacy Proxy Network** - The original shared network, maintained for backward compatibility

### Network Types

- **Service-Specific Proxy Networks**
  - Created for sensitive services (e.g., `vaultwarden-proxy`, `authelia-proxy`)
  - Connected to both the service and Traefik
  - Prevents other services from directly accessing the sensitive service
  - Created automatically by the `labctl.py` script during initialization

- **Category-Based Proxy Networks**
  - Groups similar services together (e.g., `storage-proxy`, `media-proxy`)
  - Allows controlled communication between related services
  - Created automatically by the `labctl.py` script during initialization

- **Service-Specific Backend Networks**
  - Private networks for service components (e.g., `minio-backend`)
  - Not accessible from other services
  - Created automatically by the `labctl.py` script when services are started

## Security Benefits

This isolation approach provides several security benefits:

1. **Eliminated Direct Container Access**
   - Services on different proxy networks cannot communicate directly with each other
   - Each service can only communicate with Traefik via its dedicated proxy network
   - Sensitive services (like Vaultwarden password manager) are completely isolated from other services

2. **Defense in Depth**
   - Even if one service is compromised, it cannot directly reach other services
   - Multiple network layers (proxy network + backend network) provide additional security barriers
   - Services requiring mutual communication can have controlled, explicit network paths

3. **Granular Access Control**
   - Traefik middlewares control who can access services externally (e.g., `localaccess@file`)
   - Network-level isolation prevents internal lateral movement between services
   - Category-based networks allow controlled sharing where appropriate

## Isolated Services

The following sensitive services have dedicated proxy and backend networks:

### Credential Storage
- **Vaultwarden**: Password manager 
  - `vaultwarden-proxy` (Service-to-Traefik communication)
  - `vaultwarden-backend` (Internal service components)
- **Authelia**: Authentication server 
  - `authelia-proxy` (Service-to-Traefik communication)
  - `authelia-backend` (Internal service components)

### Data Storage
- **MinIO**: S3-compatible object storage 
  - `minio-proxy` (Service-to-Traefik communication)
  - `minio-backend` (Internal service components)
- **CouchDB**: Document database 
  - `couchdb-proxy` (Service-to-Traefik communication)
  - `couchdb-backend` (Internal service components)
- **Filebrowser**: File management 
  - `filebrowser-proxy` (Service-to-Traefik communication)
  - `filebrowser-backend` (Internal service components)
- **WebDAV**: File sharing 
  - `webdav-proxy` (Service-to-Traefik communication)
  - `webdav-backend` (Internal service components)

### Category Networks
Services are also organized into category-specific proxy networks:
- `security-proxy`: Authentication and security services
- `storage-proxy`: Data storage and file sharing services
- `media-proxy`: Media streaming and library services
- `monitoring-proxy`: Monitoring and observability services
- `tools-proxy`: Utility services and applications
- `ai-proxy`: AI and machine learning services

## Implementation

### Service Configuration

Each service's Docker Compose file defines its network configuration. For sensitive services, this includes:

```yaml
services:
  server:
    # ... service configuration ...
    networks:
      - vaultwarden-proxy        # Service-specific proxy network for Traefik communication
      - vaultwarden-backend      # Service-specific backend network
    labels:
      traefik.enable: true
      traefik.docker.network: vaultwarden-proxy  # Tell Traefik which network to use
      # ... other Traefik labels ...

networks:
  vaultwarden-proxy:
    external: true               # Created by the labctl.py script
  vaultwarden-backend:
    external: false              # Created when the service is started
```

### Traefik Configuration

Traefik is configured to connect to all service-specific proxy networks:

```yaml
services:
  traefik:
    # ... service configuration ...
    networks:
      - proxy                    # Legacy network
      - vaultwarden-proxy        # Service-specific proxy networks
      - authelia-proxy
      - minio-proxy
      # ... other proxy networks ...

networks:
  proxy:
    external: true
  vaultwarden-proxy:
    external: true
  authelia-proxy:
    external: true
  minio-proxy:
    external: true
  # ... other networks ...
```

### Automatic Network Creation

The `labctl.py` script manages all network creation:

1. During initialization, it creates:
   - The default `proxy` network
   - All category-based proxy networks (`security-proxy`, `storage-proxy`, etc.)
   - All service-specific proxy networks for sensitive services

2. When starting a service, it checks if the service is in the sensitive list and creates:
   - Service-specific proxy network (if needed)
   - Service-specific backend network
   - Category-based proxy network (if applicable)

## Further Improvements

Potential future enhancements to the network isolation strategy:

1. **Migration of Remaining Services**
   - Systematically convert all services to use the new network isolation pattern
   - Create a migration plan for transitioning away from the shared `proxy` network

2. **Enhanced Network Security**
   - Consider using Docker's `--internal` flag for backend networks
   - Implement network policies using Docker's built-in capabilities
   - Add network access control lists to further restrict communication

3. **Monitoring and Intrusion Detection**
   - Add network flow monitoring to detect unusual traffic patterns
   - Implement container security monitoring
   - Add alerts for unexpected cross-network communication attempts

4. **Automation and Testing**
   - Create automated tests to verify network isolation is working
   - Develop validation scripts to check service configuration compliance
   - Add penetration testing tools to verify security boundaries

5. **Documentation and Standards**
   - Create templates for new services with proper network isolation
   - Document standard patterns for different types of services
   - Create a network architecture diagram for easier visualization