+++
archetype = "home"
title = ""
+++

## Intro

Principles:
- Automate everything -- "Keep cattle, not pets"
- Priorize local, cloud independent functionality --- Minimal cloud dependency
- Minimal, energy efficient hardware
- Avoid overcomplication -- No k8s
- Extensibility, easy configuration
- Think about security

## Key software components & services

Local infrastructure components:
- [Proxmox Virtual Environment](pve) -- Type 1 hypervisor
- Ubuntu Server -- Docker & admin tools host
- Ansible -- Configuration of the host OS & required software
- Docker Compose -- Configure Docker containers
- Traefik -- Reverse proxy with TLS certificate
- Homepage -- Dashboard

Cloud services (external dependencies):
- [OVHcloud](https://www.ovhcloud.com/en/) -- Domain Name registration
- [Cloudflare](https://www.cloudflare.com/) -- DNS zone administration, tunnel
- [Let's Encrypt](https://letsencrypt.org/) -- TLS certificate (managed by Traefik)
- [Backblaze B2](https://www.backblaze.com/cloud-storage) -- Backup storage
- [CrowdSec](https://app.crowdsec.net/) -- Crowd-sourced IP blocklist
- [Azure](https://azure.microsoft.com/) -- Temporal VM, storage
- Docker images
- Plugins (e.g. Crowdsec)
- Icons

## Directory structure

- `ansible` -- Configuration of the host OS & required software
  - `ansible/inventory` -- Host specific environment configuration
- `docker/stacks` -- Docker Compose files organized into categories
  - `docker/hosts` -- Host specific service configuration
- `terraform` -- contains an Azure VM configured for running Docker

```
$ tree -d -L 4
.
├── ansible
│   ├── inventory
│   │   └── group_vars
│   │       ├── all
│   │       ├── docker_hosts
│   │       ├── mac
│   │       └── minimal
│   └── playbooks
│       ├── debian
│       │   ├── base
│       │   ├── developer
│       │   └── docker-host
│       └── mac
│           └── base
├── docker
│   ├── hosts
│   │   ├── example
│   │   ├── nas
│   │   └── nest
│   └── stacks
│       ├── arr
│       ├── backup
...
```

## Development

Code quality scanning tools are set up via [pre-commit](https://pre-commit.com).
Perform the checks by running `lint.sh`.

## EOL

> A crowd-sourced guide to help techs help their non-tech spouses / partners / parents / kids when we are at the end-of-life

[End-of-life Disaster Response](https://github.com/potatoqualitee/eol-dr?tab=readme-ov-file)
