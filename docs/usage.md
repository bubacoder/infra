# Usage

## Most important URLs

- Dashboard: `https://home.<domain>/`

Fallback (when Traefik reverse pyoxy is not yet configured):
- Proxmox direct access: `https://<proxmox_host>:8006/`
- Portainer direct access: `http://<docker_host>:9000/`

## External access

- CloudFlare tunnel for web based RDP&SSH access (via [Guacamole](https://guacamole.apache.org/)): `https://connect.<domain>/`
- Speedtest: `https://speedtest.<domain>/`
- Wireguard VPN:
  - Admin interface: `https://vpn.<domain>/`
  - Access: host: `vpn.<domain>`, port: `51820`
