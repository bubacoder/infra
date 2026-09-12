# Getting Started<!-- omit in toc -->

- [Online service setup](#online-service-setup)
- [Local configuration](#local-configuration)
  - [1. Install Proxmox Virtual Environment](#1-install-proxmox-virtual-environment)
  - [2. Setup development/admin environment](#2-setup-developmentadmin-environment)
    - [Option A - Use devcontainer (easy method)](#option-a---use-devcontainer-easy-method)
    - [Option B - Use a dev/admin host](#option-b---use-a-devadmin-host)
  - [3. Install Ubuntu Server VM (Docker host)](#3-install-ubuntu-server-vm-docker-host)
  - [4. Install and configure the required software using Ansible](#4-install-and-configure-the-required-software-using-ansible)
  - [5. Configure Docker environment files](#5-configure-docker-environment-files)
  - [6. Prepare the Docker host repository](#6-prepare-the-docker-host-repository)
  - [7. Configure core services](#7-configure-core-services)
  - [8. Start the containers](#8-start-the-containers)
  - [9. Configure the router](#9-configure-the-router)
  - [10. Configure additional infrastructure services](#10-configure-additional-infrastructure-services)

## Online service setup

This setup uses a public domain name to allow publishing local services and to have a recognized TLS certificate.
An alternative is to use free subdomains (e.g. duckdns.org) but their support is not included in this setup.

1. Register a Domain Name, e.g. at [OVHcloud](https://www.ovhcloud.com/en/) - but the registrar does not matter, see next step
2. Transfer the DNS Zone administration to [Cloudflare](https://www.cloudflare.com/application-services/products/dns/) - Traefik reverse proxy certificate renewal is configured to use Cloudflare

## Local configuration

The recommended setup is to install Proxmox VE and deploy a Debian- or Ubuntu-based VM to host the Docker services.
For development and administrative purposes, a separate VM can be used with additional tools installed. This separation from the Docker host is a best practice, but to simplify the setup these two roles can be unified.

### 1. Install Proxmox Virtual Environment

--> See [Proxmox VE](../vm/proxmox/README.md)

### 2. Setup development/admin environment

#### Option A - Use devcontainer (easy method)

The repository includes a [Dev Container](https://code.visualstudio.com/docs/devcontainers/containers) configuration.
Using Visual Studio Code, the [Dev Containers Extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) and Docker, the development (e.g. adding more services, building the documentation) and administration tasks (e.g. running an Ansible playbook) can be performed on any environment without additional software installation.

Follow the [Dev Containers tutorial](https://code.visualstudio.com/docs/devcontainers/tutorial) to get started.
For troubleshooting, tips and tricks see [Dev Containers](../.devcontainer/README.md).

Note: The resulting container image is quite large (4+ GB) as it includes all software configured in `ansible/inventory/group_vars/debian/vars.yaml`.

#### Option B - Use a dev/admin host

The development/administrative host is used for the initial configuration and for development.

Supported OS: Debian/Ubuntu (even in [WSL](https://learn.microsoft.com/en-us/windows/wsl/)).
MacOS is also supported, but only for working with Ansible remotely and applying the `mac_base` role locally.

Steps:
- Clone the repository on a supported OS: `git clone <repository url>`
- Install Ansible with: `sudo ansible/bootstrap-ansible.sh`
  - Complete guide: [Ansible setup steps](../ansible/README.md#setup-steps)
- Update the configuration files:
  - `ansible/inventory/group_vars/debian/vars.yaml`
    - Place the SSH public key at the path indicated by `debian_base_ssh_key_file` (e.g. `~/.ssh/id_ed25519.pub`)
  - `config/ansible/inventory/inventory.yaml`
    - Copy the [inventory example](../config-example/ansible/inventory/inventory.yaml), add each host and its address under `debian`, then add it to the groups for the roles it needs. This ignored overlay keeps host-specific addresses out of tracked files.
- Apply the playbook locally: `ansible/apply-localhost.sh --ask-become-pass`
  - (After passwordless sudo is configured, the `--ask-become-pass` parameter can be dropped)

### 3. Install Ubuntu Server VM (Docker host)

Use the automated cloud-image workflow:

```bash
task vm:ubuntu-cloud-init
# Edit config/vm/proxmox/ubuntu-cloud.env
task vm:ubuntu-cloud-provision
```

Reserve the VM's DHCP lease before adding it to the Ansible inventory. See
[Ubuntu VM installation](../vm/proxmox/ubuntu.md) for configuration and alternatives.

### 4. Install and configure the required software using Ansible

Required and recommended software (like Docker, tmux, ...) are installed and configured by Ansible.
See the [Ansible README](../ansible/README.md) for details on roles, inventories, and useful run options (`--limit`, `--verbose`).

Execute on the admin host:
`ansible/apply-homelab.sh --limit <host>`

Use a host limit for a new deployment so the playbook does not apply to unrelated
inventory hosts. Omit the limit only when applying the intended configuration to all
managed hosts.

### 5. Configure Docker environment files

Docker Compose's variables are defined in `.env` files with different scopes:

| File                                            | Purpose                                                   |
| ----------------------------------------------- | --------------------------------------------------------- |
| `config/docker/.env`                            | Common variables, can be used in all hosts and services   |
| `config/docker/.env.<service_name>`             | Variables scoped to a service                             |
| `config/docker/<host_name>/.env`                | Host-specific variables                                   |
| `config/docker/<host_name>/.env.<service_name>` | Variables scoped to a specific service on a specific host |

Create the ignored Docker configuration directory from the examples:

```bash
mkdir -p config/docker
cp -a config-example/docker/. config/docker/
```

The trailing `/.` includes the common `.env` file. Replace all example values before
deployment. Put credentials only in the ignored `config` directory or the password
vault, never in tracked files or commands.

Keep `config` in a private Git repository shared by the administrative host and Docker
hosts. On an existing deployment, clone that private repository into `config` before
editing it. For a first deployment, create the directory from the examples above, then
initialize and push it to a private repository using the organization's approved Git
workflow. Docker hosts should use read-only, host-specific deploy keys for this
repository.

Warning: The files in the `config` folder are not committed to the repository (see: `.gitignore`) because they contain sensitive information.
Ensure these files are backed up! For this, use `task backup-config` and store the generated backup file securely.

Sample folder structure:

```
config/docker
├── .env
├── nas
│   ├── services.yaml
│   └── .env
└── nest
    ├── services.yaml
    └── .env
```

### 6. Prepare the Docker host repository

The Docker workflow runs on the Docker host and requires both the tracked infrastructure
repository and its private `config` repository. After Ansible has configured the host,
connect to it and clone both repositories:

```bash
mkdir -p ~/repos
git clone <infrastructure-repository-url> ~/repos/infra
git clone <private-config-repository-url> ~/repos/infra/config
```

The private configuration repository must contain the host-specific directory under
`config/docker/<hostname>/`. Do not store Git write credentials on a Docker host.

### 7. Configure core services

TODO: Separate core services, like Traefik and Homepage

TODO: Describe the minimally required core service configuration

For central authentication and SSO, see [Authentik Getting Started](authentik.md).

### 8. Start the containers

Edit `config/docker/<hostname>/services.yaml` to select which services (stacks) should be started (`state: up`)
or stopped (`state: down`).

Run these commands on the Docker host from its infrastructure repository checkout:

```bash
task pull-config-repo
task docker:apply
```

`task pull-config-repo` only accepts fast-forward updates, so it cannot create a merge
commit on the Docker host. Keep it separate from deployment to make configuration
changes and service startup explicit actions.

### 9. Configure the router

After setting up the VM, configure the following on the router:
- Fix IP (static DHCP lease) for the Docker host
- To enable external access to selected services: Port forward to the VM (In OpenWrt: Network -> Firewall -> Port Forwards)
  - HTTPS - Port 443 TCP & UDP
  - WireGuard - Port 51820 UDP
- DHCP settings: set the DNS server address to the IP of your AdGuard Home service (set both instances if you are using AdGuard Home Sync)
- Configure the local DNS service to resolve your domain name to the main Docker host. This is to provide uninterrupted DNS name resolution of the local services in case of the internet access fails.
  - In AdGuard Home: Filters -> DNS Rewrites -> Add <hostname> AND *.<hostname>

Note: Query and refresh IP configuration on Windows:
```sh
ipconfig /all
ipconfig /release && ipconfig /renew
```

### 10. Configure additional infrastructure services

TODO: Describe configuration

- AdGuard: local domain, router DHCP
- Cloudflare
- Monitoring
- Backup
