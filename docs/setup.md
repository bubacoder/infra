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
  - [6. Configure core services](#6-configure-core-services)
  - [7. Start the containers](#7-start-the-containers)
  - [8. Configure the router](#8-configure-the-router)
  - [9. Configure additional infrastructure services](#9-configure-additional-infrastructure-services)

## Online service setup

This setup uses a public domain name to allow publishing local services and to have a recognized TLS certificate.
An alternative is to use free subdomains (e.g. duckdns.org) but their support is not included in this setup.

1. Register a Domain Name, e.g. at [OVHcloud](https://www.ovhcloud.com/en/) - but the registrar does not matter, see next step
2. Transfer the DNS Zone administration to [Cloudflare](https://www.cloudflare.com/application-services/products/dns/) - Traefik reverse proxy certificate renewal is configured to use Cloudflare

## Local configuration

The recommended setup is to install Proxmox VE and deploy a Debian- or Ubuntu-based VM to host the Docker services.
For development and administrative purposes, a separate VM can be used with additional tools installed. This separation from the Docker host is a best practice, but to simplify the setup these two roles can be unified.

### 1. Install Proxmox Virtual Environment

--> See [Proxmox VE](../proxmox/README.md)

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
- Install Ansible with: `ansible/bootstrap-ansible.sh`
- Edit `ansible/inventory/inventory.yaml` and `ansible/playbooks/homelab.yaml`, include your host with `markosamuli.linuxbrew` and `debian_developer` roles
- Run `ansible/apply-homelab.sh`

### 3. Install Ubuntu Server VM (Docker host)

Edit the parameters and use the `proxmox/create-ubuntu-server-vm.sh` script to automatically create an Ubuntu Server LTS virtual machine and start the OS installation.

Note - Alternatives:
- Create the VM using the Proxmox web interface, download and attach the installer ISO, then proceed with manual installation
- Use Terraform to deploy the VM via the [Proxmox Terraform provider](https://registry.terraform.io/providers/Telmate/proxmox/latest/docs)
- Install Ubuntu as an LXC container (note that there may be some limitations)

### 4. Install and configure the required software using Ansible

Required and recommended software (like Docker, tmux, ...) are installed and configured by Ansible.
For details, check the `ansible` / `inventory`|`roles`|`playbooks` folders.

Execute on the admin host:
`ansible/apply-homelab.sh`

### 5. Configure Docker environment files

Docker Compose's variables are defined in `.env` files with different scopes:

| File                                            | Purpose                                                   |
| ----------------------------------------------- | --------------------------------------------------------- |
| `config/docker/.env`                            | Common variables, can be used in all hosts and services   |
| `config/docker/.env.<service_name>`             | Variables scoped to a service                             |
| `config/docker/<host_name>/.env`                | Host-specific variables                                   |
| `config/docker/<host_name>/.env.<service_name>` | Variables scoped to a specific service on a specific host |

Copy `config-example/docker/*` to `config/docker/*` as a starting point of configuration of the Docker-based services.

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

### 6. Configure core services

TODO: Separate core services, like Traefik and Homepage

TODO: Describe the minimally required core service configuration

### 7. Start the containers

Edit `config/docker/<hostname>/services.yaml` to select which services (stacks) should be started (`state: up`)
or stopped (`state: down`).

To apply the changes run `task docker:apply`.

### 8. Configure the router

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

### 9. Configure additional infrastructure services

TODO: Describe configuration

- AdGuard: local domain, router DHCP
- Cloudflare
- Monitoring
- Backup
