# Getting Started<!-- omit in toc -->

- [Before You Start](#before-you-start)
- [Online Prerequisites](#online-prerequisites)
- [Phase 1: Prepare the Admin Environment](#phase-1-prepare-the-admin-environment)
- [Phase 2: Provision the Docker Host](#phase-2-provision-the-docker-host)
- [Phase 3: Configure the Docker Host with Ansible](#phase-3-configure-the-docker-host-with-ansible)
- [Phase 4: Configure and Deploy Services](#phase-4-configure-and-deploy-services)
- [Phase 5: Configure Networking](#phase-5-configure-networking)

This guide deploys services to a Debian- or Ubuntu-based Docker host, normally a
VM on Proxmox VE. It identifies where each command runs so the same workflow
supports a combined Docker and admin host or a separate admin host.

## Before You Start

### Roles

| Role | Responsibility | Can be combined? |
| --- | --- | --- |
| Proxmox host | Runs the Docker-host VM | Separate from the Docker host |
| Admin environment | Holds the infrastructure and private configuration repositories; runs Ansible | May be the Docker host |
| Docker host | Runs Docker Compose services | May be the admin environment |

The **admin environment** may be a separate Debian/Ubuntu workstation, a
devcontainer running on that workstation, or the Docker host itself. A separate
admin environment is recommended for a persistent deployment because the Docker
host needs only read-only access to the private configuration repository. A new
Docker-host VM needs a temporary admin environment until it is provisioned; it
can become the admin environment afterwards in single-host mode.

Choose one of these operating models before continuing:

| Model | Admin environment | Docker host | Ansible command |
| --- | --- | --- | --- |
| Single-host | Docker host | Same machine | `ansible/apply-localhost.sh` |
| Separate admin host | Admin workstation or devcontainer | Separate VM | `ansible/apply-homelab.sh --limit <host>` |

In single-host mode, follow every step labelled **Admin environment** and
**Docker host** on the same machine. In separate-admin-host mode, use SSH to run
the Docker-host steps after Ansible has configured the VM.

### Workflow Order

| Model | Follow this order |
| --- | --- |
| Single-host with a new VM | Use a temporary admin environment for Phase 2, then complete Phases 1, 3, 4, and 5 on the new Docker host. |
| Single-host with an existing Docker host | Complete Phases 1, 3, 4, and 5 on that host. |
| Separate admin host | Complete Phases 1, 2, and 3 from the admin environment, then complete Phases 4 and 5 on the Docker host. |

### Command Locations

- **Admin environment:** A machine or devcontainer that runs Ansible and keeps
  the private configuration repository.
- **Proxmox host:** The hypervisor that creates and runs the Docker-host VM.
- **Docker host:** The VM that runs the container services.

## Online Prerequisites

This setup uses a public domain name for published services and recognized TLS
certificates. Free subdomains such as DuckDNS can work, but are not covered by
this setup.

1. Register a domain name, for example with [OVHcloud](https://www.ovhcloud.com/en/).
2. Transfer DNS zone administration to [Cloudflare](https://www.cloudflare.com/application-services/products/dns/).
   Traefik uses Cloudflare for DNS-01 certificate renewal.

## Phase 1: Prepare the Admin Environment

**Where:** Admin environment

In single-host mode, use a temporary admin environment to provision the Docker
host, then complete this phase on the Docker host. In separate-admin-host mode,
complete it on the dedicated admin workstation before provisioning or
configuring the Docker host.

### Choose the Tooling Environment

Use one of these options:

- **Devcontainer:** The repository includes a [Dev Container](https://code.visualstudio.com/docs/devcontainers/containers)
  configuration. Use the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
  with Visual Studio Code. See [Dev Containers](../.devcontainer/README.md) for
  troubleshooting. The image is large because it includes the administration
  tooling configured in `ansible/inventory/group_vars/debian/vars.yaml`.
- **Local tools:** Use Debian/Ubuntu, including WSL. macOS supports remote
  Ansible administration and the local `mac_base` role.

### Prepare Repositories and Ansible

Clone the infrastructure repository and bootstrap Ansible:

```bash
git clone <infrastructure-repository-url> ~/repos/infra
cd ~/repos/infra
sudo ansible/bootstrap-ansible.sh
```

Create the ignored configuration overlay from its examples, then edit the
inventory and shared variables:

```bash
mkdir -p config
cp -a config-example/ansible config/
```

- Add each host and address to `config/ansible/inventory/inventory.yaml` under
  `debian`, then assign the host to the groups for its required roles.
- For a newly provisioned VM, set its `ansible_user` to the same username as
  `USERNAME` in `config/vm/proxmox/ubuntu-cloud.env`. Ansible uses this account
  as the managed administrator by default. Override `admin_user` per host only
  when the connection and managed accounts must differ.
- Set `debian_base_ssh_key_file` in
  `ansible/inventory/group_vars/debian/vars.yaml` and place the matching public
  key at that path, for example `~/.ssh/id_ed25519.pub`.
- For a separate Docker host, add its current DHCP address as `ansible_host`
  in the ignored inventory for the initial Ansible run. It is safe to use this
  address before DNS is configured. Reserve the DHCP lease and configure the
  hostname in local DNS in [Phase 5](#phase-5-configure-networking), then
  update the inventory to use the hostname.
- Connect once with `ssh <initial-user>@<dhcp-address>` and verify the host
  key before running Ansible. Do not disable SSH host-key verification.

See the [Ansible README](../ansible/README.md) for inventory structure,
bootstrap authentication, and troubleshooting options.

## Phase 2: Provision the Docker Host

**Where:** Admin environment and Proxmox host

Install Proxmox VE first. See [Proxmox VE](../vm/proxmox/README.md).

From the infrastructure checkout on the admin environment, use the automated
cloud-image workflow:

```bash
task vm:ubuntu-cloud-init
# Edit config/vm/proxmox/ubuntu-cloud.env
task vm:ubuntu-cloud-preflight
task vm:ubuntu-cloud-provision
```

The tasks connect to the Proxmox host and create the VM. Reserve its DHCP lease
before the Ansible phase. For prerequisites, configuration, and autoinstall or
manual alternatives, see [Ubuntu VM installation](../vm/proxmox/ubuntu.md).

Skip this phase only when an existing machine will be the Docker host.

## Phase 3: Configure the Docker Host with Ansible

**Where:** Admin environment

Ansible configures Docker and the required host software. The Docker host must
be present in the inventory and the `docker_hosts` group.

For a separate Docker host, run:

```bash
ansible/apply-homelab.sh --limit <host>
```

For single-host mode, run this on the Docker host after its inventory hostname
has been assigned to `docker_hosts`:

```bash
ansible/apply-localhost.sh
```

Use `--ask-become-pass` when the initial account requires a sudo password. Use
a host limit for a new remote deployment so the playbook does not apply to
unrelated inventory hosts.

## Phase 4: Configure and Deploy Services

### Prepare Docker-Host Repositories

**Where:** Docker host

The Docker host needs the tracked infrastructure repository and configuration.
For a separate admin environment, give the Docker host a read-only deploy key
to the private configuration repository:

```bash
mkdir -p ~/repos
git clone <infrastructure-repository-url> ~/repos/infra
git clone <private-config-repository-url> ~/repos/infra/config
cd ~/repos/infra
task docker:check-host
```

The private configuration repository must contain
`config/docker/<hostname>/`. Do not store Git write credentials on a Docker
host.

For a single-host installation without a private configuration repository, use
the local initializer instead:

```bash
cd ~/repos/infra
task docker:init-local-config
task docker:check-host
```

The initializer creates a minimal Traefik and Homepage profile and refuses to
overwrite an existing host configuration.

### Configure Environment Files

Docker Compose variables use four scopes. `labctl.py` loads each existing file
in this order, so later files override earlier values:

| File | Purpose |
| --- | --- |
| `config/docker/.env` | Common variables for every host and service |
| `config/docker/<hostname>/.env` | Host-specific variables |
| `config/docker/.env.<service-name>` | Common service-specific variables |
| `config/docker/<hostname>/.env.<service-name>` | Host- and service-specific variables |

For a shared configuration repository, seed `config/docker` on the admin
environment from the examples before committing it to the private repository:

```bash
mkdir -p config/docker
cp -a config-example/docker/. config/docker/
```

Replace all example values before deployment. Keep credentials only in ignored
`config` files or the password vault, never in tracked files or commands. Back
up the private configuration repository and use `task backup-config` for an
offline copy stored securely.

Example layout:

```text
config/docker
├── .env
├── .env.<service-name>
└── <hostname>
    ├── .env
    ├── .env.<service-name>
    └── services.yaml
```

### Configure Core Services

The minimal local profile selects Traefik and Homepage. Add other services to
`config/docker/<hostname>/services.yaml` only after completing their
configuration and secret requirements.

For a host using `test.example.com`, set these shared values in
`config/docker/.env`:

```dotenv
MYDOMAIN=test.example.com
MYDOMAIN_TLS_SANS=*.${MYDOMAIN}
ADMIN_EMAIL=<Let's Encrypt registration email>
CLOUDFLARE_DNS_API_TOKEN=<store in the password vault or ignored config only>
```

Set these host-specific values in `config/docker/<hostname>/.env`:

```dotenv
DOCKER_VOLUMES=/mnt/docker-volumes
CROWDSEC_ENABLED=false
```

`CLOUDFLARE_DNS_API_TOKEN` needs `Zone:Read` and `DNS:Edit` permissions for the
zone containing `MYDOMAIN`. Keep `CROWDSEC_ENABLED=false` for a minimal local
deployment. Set it to `true` only after deploying CrowdSec and generating
`CROWDSEC_BOUNCER_API_KEY` in `config/docker/<hostname>/.env.traefik`.

For central authentication and SSO, see [Authentik Getting Started](authentik.md).

### Deploy Services

**Where:** Docker host

Select services in `config/docker/<hostname>/services.yaml` with `state: up`

```bash
task docker:apply
```

When `config` is a private Git repository, synchronize it before deploying:

```bash
task pull-config-repo
task docker:apply
```

`task pull-config-repo` accepts only fast-forward updates, keeping configuration
updates and deployments as separate actions. For a local-only `config`
directory, run `task docker:apply` directly.

## Phase 5: Configure Networking

**Where:** Router and local DNS service

Configure the following after the Docker host is online:

- Reserve a static DHCP lease for the Docker host.
- Configure local DNS to resolve `test.example.com` and `*.test.example.com` to
  the Docker host. In AdGuard Home, use **Filters > DNS Rewrites**.
- Set router DHCP clients to use the local DNS service, such as AdGuard Home.
- For external access only, forward HTTPS ports `443/TCP` and `443/UDP` to the
  Docker host. Forward `51820/UDP` only when using WireGuard.

Cloudflare DNS-01 lets Traefik create temporary `_acme-challenge` records for
Let's Encrypt. Public DNS records and port forwarding are not required for
local-only HTTPS access.
