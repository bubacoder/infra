# Getting Started<!-- omit in toc -->

The preferred approach is to use virtualization.

- [Online service setup](#online-service-setup)
- [Local configuration](#local-configuration)
  - [1. Install Proxmox Virtual Environment](#1-install-proxmox-virtual-environment)
  - [2. Setup admin host](#2-setup-admin-host)
  - [3. Install Ubuntu Server VM (Docker host)](#3-install-ubuntu-server-vm-docker-host)
  - [4. Install and configure the requred software using Ansible](#4-install-and-configure-the-requred-software-using-ansible)
  - [5. Configure Docker environment files](#5-configure-docker-environment-files)
  - [6. Configure core/access services](#6-configure-coreaccess-services)
  - [7. Start the containers](#7-start-the-containers)

## Online service setup

This setup uses a public Domain Name to allow publishing local services and to have a recognized TLS certificate.
An alternative is to use free subdomains (e.g. duckdns.org) but its support is not included in this lab setup.

1. Register a Domain Name, e.g. at [OVHcloud](https://www.ovhcloud.com/en/) - but the registrar does not matter, see next step
2. Transfer the DNS Zone administration to [Cloudflare](https://www.cloudflare.com/application-services/products/dns/) - traefik reverse proxy certificate renewal is configured to use Cloudflare

## Local configuration

### 1. Install Proxmox Virtual Environment

--> See [Proxmox VE](proxmox)

### 2. Setup admin host

The administrative host is used for the initial configuration and for development.

Supported OS: Debian/Ubuntu (even in [WSL](https://learn.microsoft.com/en-us/windows/wsl/)) and MacOS.

Steps:
- Clone the repository: `git clone <repository url>`
- Install Ansible with: `ansible/bootstrap-ansible.sh`

### 3. Install Ubuntu Server VM (Docker host)

Edit and use the `infra/proxmox/create-ubuntu-server-vm.sh` script to automatically create an Ubuntu Server LTS VM and start the OS installation.

Note - Alternatives:
- Create the VM on the Proxmox GUI, download and attach the installer CD and proceed with manual installation (who does that?)
- Use Terraform to deploy the VM via the [Proxmox Terraform provider](https://registry.terraform.io/providers/Telmate/proxmox/latest/docs)
- Install Ubuntu as an LXC container (there could be some limitations)

After setting up the VM, configure the following on the router:
- Static DHCP lease for the VM
- Port forward to the VM (HTTPS, WireGuard)

### 4. Install and configure the requred software using Ansible

Required and recommended software (like docker, tmux, ...) are installed and configured by Ansible.  
For details, check the `ansible` / `inventory`|`roles`|`playbooks` folders.

Excute on the admin host:
`ansible/apply-homelab.sh`

### 5. Configure Docker environment files

Docker Compose's variables can be defined in `.env` files with different scopes:

| File                                           | Purpose                                                   |
| ---------------------------------------------- | --------------------------------------------------------- |
| `docker/hosts/.env`                            | Common variables, can be used in all hosts and services   |
| `docker/hosts/.env.<service_name>`             | Variables scoped to a service                             |
| `docker/hosts/<host_name>/.env`                | Host-specific variables                                   |
| `docker/hosts/<host_name>/.env.<service_name>` | Variables scoped to a specific service on a specific host |

Use (copy) `docker/hosts/.env.example` and `docker/hosts/example/.env` as a starting point of configuration of the Docker-based services.

Warning: The `.env*` files are not committed to the repository because they contain sensitive information (see: `.gitignore`). Ensure these files are backed up!

Sample folder structure:

```
docker/hosts
├── .env
├── example
│   ├── apply.sh
│   └── .env
├── nas
│   ├── apply.sh
│   └── .env
└── nest
    ├── apply.sh
    └── .env
```

### 6. Configure core/access services

- Traefik
- Domain
- DNS
- Configure router (DNS, port forwarding)
- TLS cert
- Cloudflare
- Monitoring
- Backup

TODO Describe the minimally required configuration.

### 7. Start the containers

Edit `docker/hosts/<hostname>/apply.sh` to select which services (stacks) should be started (`up` function)
or stopped (`down` fuction).

To apply the changes run run `task docker-apply` or `docker/hosts/<hostname>/apply.sh`.
