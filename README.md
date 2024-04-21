+++
archetype = "home"
title = ""
+++

# Homelab<!-- omit in toc -->

- [Goals](#goals)
  - [**Learning**, knowledge organization](#learning-knowledge-organization)
  - [**Independence** from external resources](#independence-from-external-resources)
  - [Principles](#principles)
- [Key software components \& services](#key-software-components--services)
  - [Local infrastructure components](#local-infrastructure-components)
  - [Cloud services (external dependencies)](#cloud-services-external-dependencies)
- [Directory structure](#directory-structure)
- [Development](#development)
- [EOL](#eol)

## Goals

### **Learning**, knowledge organization

### **Independence** from external resources

### Principles

- Automate everything -- "Keep cattle, not pets"
- Priorize local, cloud independent functionality --- Minimal cloud dependency
- Minimal, energy efficient hardware
- Avoid overcomplication -- No k8s
- Extensibility, easy configuration
- Think about security

## Key software components & services

### Local infrastructure components

- [Proxmox Virtual Environment](pve) -- Type 1 hypervisor
- Ubuntu Server -- Docker & admin tools host
- Ansible -- Configuration of the host OS & required software
- Docker Compose -- Configure Docker containers
- Traefik -- Reverse proxy with TLS certificate
- Authelia -- Authentication, Single Sign On
- [Guacamole](https://guacamole.apache.org/) -- Web based Remote Desktop and SSH access
- Homepage -- Dashboard

### Cloud services (external dependencies)

| Name                                                    | Description                            | Remarks                                                          |
| ------------------------------------------------------- | -------------------------------------- | ---------------------------------------------------------------- |
| Docker images                                           | All services are running as containers | Downloaded on first use                                          |
| Plugins, Modules (e.g. Crowdsec)                        | Various plugins for services           | Downloaded on first use. TODO create inventory                   |
| Large Language Models                                   | Optional, used by Ollama               | Downloaded on first use                                          |
| [OVHcloud](https://www.ovhcloud.com/en/) (or other)     | Domain Name registration               | Required for remote access and TLS certs. TODO document fallback |
| [Cloudflare](https://www.cloudflare.com/)               | DNS zone administration, tunnel        | Optional, for remote access                                      |
| [Let's Encrypt](https://letsencrypt.org/)               | TLS certificate (managed by Traefik)   | Required. TODO document local CA setup for fallback              |
| [Backblaze B2](https://www.backblaze.com/cloud-storage) | Backup storage                         | Optional, local backup also configured                           |
| [CrowdSec](https://app.crowdsec.net/)                   | Crowd-sourced IP blocklist             | Optional, security service, can be disabled                      |
| [Azure](https://azure.microsoft.com/)                   | Temporal VM, storage                   | Optional, not used by any lab components                         |
| Homepage Icons                                          | Icon set for the services              | Optional, hosted on a CDN. TODO host locally                     |

## Directory structure

- `ansible` -- Configuration of the host OS & required software
  - `ansible/roles` -- Roles for Debian-based Docker & admin hosts and a Mac-based DevOps/SRE toolset
  - `ansible/inventory` -- Host specific environment configuration
- `docker` -- Docker-based service configuration
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

> A crowd-sourced guide to help techs help their non-tech spouses / partners / parents / kids when we are at the end-of-life.

[End-of-life Disaster Response](https://github.com/potatoqualitee/eol-dr?tab=readme-ov-file)
