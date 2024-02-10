+++
archetype = "home"
title = ""
+++

# Intro

Elvek
Minimal cloud dependency
Avoid overcomlication (no K8s...)
Automate, reusable
Minimal hardware (cost)
Local access priority
Security
Extensive

## Key software components & services

- [Proxmox Virtual Environment](pve) -- Type 1 hypervisor
- Ubuntu Server -- Admin & Docker host
- Ansible -- Configuration of the OS & required software
- Docker Compose -- Configure and run containers
- Traefik -- Reverse proxy
- Homepage -- Dashboard
- OVH -- Domain Name
- Cloudflare -- DNS zone administration
- Let's Encrypt -- TLS certificate

## Directory structure

- `ansible`
  - `ansible/inventory`
- `docker/stacks` -- Docker Compose files organized into categories
  - `docker/hosts` --
- `terraform` -- contains an Azure VM configured for running Docker - currently outdated

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
│       ├── dashboard
│       │   └── homepage
│       ├── dev
│       ├── fileshare
│       │   └── qbittorrent
│       ├── infra
│       ├── media
│       │   ├── audio
│       │   ├── ebook
│       │   ├── photo
│       │   └── video
│       ├── monitoring
│       │   └── prometheus
│       ├── personal
│       │   └── misikoli-web
│       ├── security
│       │   ├── authelia
│       │   ├── crowdsec
│       │   └── traefik
│       ├── smarthome
│       ├── storage
│       │   └── filebrowser
│       ├── tools
│       └── wip
│           ├── core
│           ├── game
│           └── tools
├── docs
│   └── web
│       ├── archetypes
│       ├── content
│       │   └── docker
│       └── public
│           ├── categories
│           ├── css
│           ├── docker
│           ├── fonts
│           ├── js
│           ├── pve
│           ├── tags
│           ├── terraform
│           ├── webfonts
│           └── website
├── homedir
│   └── scripts
└── terraform
    └── modules
        ├── base
        ├── nest
        │   ├── cloud-init
        │   └── compose
        └── storage
```

## External Dependencies

DNS, Cert, Backup, Icons, Docker images, Plugins

## Repo cleanup

https://github.com/newren/git-filter-repo/blob/main/INSTALL.md
https://github.com/newren/git-filter-repo/blob/main/Documentation/converting-from-bfg-repo-cleaner.md#cheat-sheet-conversion-of-examples-from-bfg

## Bouncer

https://www.smarthomebeginner.com/crowdsec-docker-compose-1-fw-bouncer/
