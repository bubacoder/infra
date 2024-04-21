# Getting started

## Cloud accounts

This setup uses a public Domain Name to allow publishing local services and to have a recognized TLS certificate.
An alternative is to use free subdomains (e.g. duckdns.org) but its support is not included in this lab setup.

1. Register a Domain Name, e.g at [OVHcloud](https://www.ovhcloud.com/en/) - but the registrar does not matter, see next step
2. Transfer the DNS Zone administration to [Cloudflare](https://www.cloudflare.com/application-services/products/dns/) - traefik reverse proxy certificate renewal is configured to use Cloudflare

## Overview of local setup

1. Install type 1 virtualization - Proxmox VE
2. Install & configure Admin host
3. Install Docker host
4. Configure Docker host with Ansible
5. Setup .env file for the Docker host(s)
6. Configure core/access services
7. Configure workloads

## Install Proxmox Virtual Environment

--> See [Proxmox VE](pve)

## Setup admin host

Supported: Linux/WSL/MacOS

Steps:
- Clone the repository: `git clone <repository url>`
- Install Ansible with: `bootstrap-ansible.sh`

## Install Ubuntu Server VM (Docker host)

Currently the VM is manually created and the OS (Ubuntu Server LTS or Debian) is manually installed.

Alternatives:
- Use Terraform to deploy the VM (Proxmox Terraform provider: https://registry.terraform.io/providers/Telmate/proxmox/latest/docs)
- Use LXC

Proxmox settings:
- Autostart the VM

Router settings:
- Static DHCP lease for the VM
- Port forward to the VM (HTTPS, WireGuard)

## Run Ansible to set up dependencies in the VM(s)

Excute on the admin host:
`ansible/apply-homelab.sh`

## Add .env file

The `.env` files are not committed to the repository (see: .gitignore). Backup these files!

```
hosts
├── example
├── nas
│   ├── apply.sh
│   └── .env
└── nest
    ├── apply.sh
    └── .env
```

### Configure core/access services

- Traefik
- Domain
- DNS
- Configure router (DNS, port forwarding)
- TLS cert
- Cloudflare
- Monitoring
- Backup

## Start containers

`docker/hosts/<hostname>/apply.sh`
