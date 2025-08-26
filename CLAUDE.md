# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains Infrastructure as Code (IaC) configuration for a home infrastructure setup. The main goals are:
- Creating a local, self-hosted environment for various services minimizing reliance on cloud providers
- Learning and organizing knowledge, best practices, and tool documentation

## Key Commands

### Development and Building

```bash
# List all available tasks
task --list-all

# Run all linting and build tasks
task build

# Run linting tools on all files (via pre-commit)
task lint

# Open TaskUI (terminal UI for executing tasks)
task ui

# Clear generated content and cache data
task clean
```

### Docker Management

```bash
# Deploy locally configured containers
task docker:apply

# Update and restart containers
task docker:update

# Pull container images
task docker:pull

# Pull, update, restart containers, then show restarts
task docker:pull-update

# Stop configured containers
task docker:stop

# Remove unused and dangling images
task docker:prune

# Show docker disk usage
task docker:du
```

### Ansible Commands

```bash
# Run Ansible for homelab setup
ansible/apply-homelab.sh

# Run Ansible for cloud setup
ansible/apply-cloud.sh

# Run Ansible for Mac workstation setup
ansible/apply-mac-workstation.sh
```

## Architecture Overview

The infrastructure is designed around the following components:

1. **Core Infrastructure**:
   - Proxmox Virtual Environment as a Type 1 hypervisor
   - Ubuntu Server as the host OS for Docker containers
   - Ansible for configuration management
   - Docker Compose for container definitions

2. **Key Services**:
   - **Security**: Traefik (reverse proxy), Authelia (authentication), Cloudflared (tunnel)
   - **Monitoring**: Grafana, Prometheus, Node-exporter, Uptime-kuma
   - **Media**: Jellyfin, Metube, Navidrome, Calibre
   - **Storage**: MinIO, Syncthing, FileSharing
   - **AI Tools**: Ollama, Open-WebUI, LiteLLM, AutogenStudio
   - **Tools**: Guacamole, Homepage (dashboard), Vaultwarden

3. **Configuration Structure**:
   - `ansible/`: Contains playbooks and roles for infrastructure setup
   - `docker/`: Contains Docker Compose definitions for all services
   - `docs/`: Documentation and usage instructions
   - `terraform/`: IaC for cloud provisioning
     - `azure-vm/`: Azure Virtual Machine deployment with CloudInit
   - `proxmox/`: Scripts for VM creation and management
   - `scripts/`: Utility scripts for various tasks
   - `config/`: Host-specific configuration (not in repository)
   - `config-example/`: Example configuration files

## Development Workflow

This project uses:
- **Task** (taskfile.dev) as a task runner/build tool
- **Pre-commit** for code quality and security checks
- **Docker** and Docker Compose for containerized services
- **GitHub Actions** for CI/CD workflows:
  - Pre-commit checks
  - Building devcontainer
  - Building and deploying documentation site
- **Renovate** for automated dependency updates

## File Structure

Key directories and their purposes:

```
/
├── ansible/         # Ansible configuration for server setup
│   ├── playbooks/   # Main playbooks for different environments
│   └── roles/       # Individual roles for specific configurations
├── docker/          # Docker Compose files for services
│   ├── security/    # Auth and security services
│   ├── media/       # Media services
│   ├── storage/     # Storage services
│   └── monitoring/  # Monitoring services
├── docs/            # Documentation
├── terraform/       # Terraform configurations
│   └── azure-vm/    # Azure VM deployment with CloudInit
└── scripts/         # Utility scripts
```

When contributing to this repository, follow the pre-commit rules defined in `.pre-commit-config.yaml` which includes linting for shell scripts, Dockerfiles, YAML files, Ansible playbooks, and Terraform configurations.
