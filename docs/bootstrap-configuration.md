# Bootstrap Configuration Draft

This document records the inputs and file mappings observed while testing the
first-time installation process. It is the input contract for a future
non-secret bootstrap YAML and Python orchestrator; it is not yet an executable
configuration format.

## Proposed YAML

```yaml
version: 1

repository:
  url: <infrastructure-repository-url>
  branch: bootstrap

deployment:
  admin_model: separate
  core_profile: local-core

proxmox:
  ssh_target: <user-or-ssh-alias>
  vm:
    id: <preferred-id-or-auto>
    name: <hostname>
    os: ubuntu
    os_version: "26.04"
    username: admin
    cpu_cores: 4
    memory_max_mib: 4096
    memory_min_mib: 1024
    disk_size: 256G
    storage: local-lvm
    bridge: vmbr0
    ssh_public_key: <public-key-path-or-fingerprint>

host:
  docker_volumes: /srv/docker-volumes
  timezone: Etc/UTC

network:
  address_mode: dhcp
  reservation: required-external
  domain: <public-base-domain>
  local_dns: required-external
  external_https: false
  wireguard: false

tls:
  provider: cloudflare
  acme_email: <registration-email>
  token_ref: <vault-reference-or-interactive-handoff>

services:
  - security/traefik
  - dashboard/homepage
```

Secret values must not be accepted directly in this file. The orchestrator
should resolve a vault reference or pause for an interactive write to an
ignored mode-`0600` file without printing the value.

## Input Destinations

| Bootstrap input | Current destination |
| --- | --- |
| Proxmox target and VM specification | `config/vm/proxmox/ubuntu-cloud.env` |
| VM hostname, initial address, and user | `config/ansible/inventory/inventory.yaml` |
| Docker role assignment | `docker_hosts` in the ignored Ansible inventory |
| SSH public-key path | `ansible/inventory/group_vars/debian/vars.yaml` or a host override |
| Docker volume path | Ansible `debian_docker_host_volumes_path` and host `DOCKER_VOLUMES` |
| Timezone, domain, and ACME email | `config/docker/.env` |
| Host Docker settings | `config/docker/<hostname>/.env` |
| Cloudflare token reference/handoff | `config/docker/<hostname>/.env.traefik` |
| Core service selection | `config/docker/<hostname>/services.yaml` |
| Repository branch | Local and Docker-host Git checkouts |
| DHCP reservation and local DNS | External router and DNS configuration |

## Required Phases

1. Validate local tools, repository branch, SSH trust, Proxmox sudo, VM-ID and
   name availability, storage, bridge, image availability, and storage risk.
2. Render ignored configuration and show a redacted plan without changing
   infrastructure.
3. Require explicit approval, create the VM, and wait with bounded timeouts for
   guest agent, DHCP, and cloud-init.
4. Verify the SSH host key through a trusted channel, update the ignored
   inventory, and run Ansible with a strict host limit.
5. Clone the selected repository branch on the Docker host, initialize minimal
   configuration, and pause for secret handoff.
6. Verify DHCP reservation and base/wildcard DNS before normal-path service
   tests; never replace an existing target without approval.
7. Deploy the selected profile and verify container stability, dependencies,
   persistence, HTTPS, certificates, DNS targets, and repeat deployment.

Every phase should be restartable without deleting an existing VM or persisted
service data. A failed readiness wait must have a non-destructive resume path.
