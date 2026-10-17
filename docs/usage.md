# Usage

For service lifecycle commands, see [Docker services](../docker/README.md#service-operations).
For destructive maintenance and recovery, see [Runbooks](runbooks.md).

## Utility commands

Run from the repository root on the intended host:

| Command | Purpose |
| --- | --- |
| `task get-public-ip` | Show the host's public IP |
| `task versions` | Show installed OS and tool versions |
| `task backup-config` | Archive the private configuration directory locally |
| `task get-offline-data` | Download offline datasets, models and VM data to configured local/Proxmox storage |

Configuration archives contain private data: protect them and never publish their
contents. For application-data backups and recovery, see [Backup and recovery](backup.md).
Offline downloads use the network and storage; inspect the task and intended hosts
before starting them.

## Most important URLs

**Dashboard (start here)**: `https://home.<domain>/`

Fallback (when Traefik reverse proxy is not yet configured):
- Proxmox direct access: `https://<proxmox_host>:8006/`
- Portainer direct access: `http://<docker_host>:9000/`

## External access

- CloudFlare tunnel for web based RDP & SSH access (via [Guacamole](https://guacamole.apache.org/)): `https://connect.<domain>/`
- Speedtest: `https://speedtest.<domain>/`
- WireGuard VPN:
  - Admin interface: `https://vpn.<domain>/`
  - Access: host: `vpn.<domain>`, port: `51820`
