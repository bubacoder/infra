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

# Create/update Docker example environment configuration files
task docker:create-example-env
```

### Service Management

```bash
# Manage individual Docker service (pull, up, down, restart, recreate, config)
scripts/labctl.py service [operation] [category/service-name]

# Examples:
scripts/labctl.py service up security/traefik
scripts/labctl.py service restart ai/ollama
scripts/labctl.py service pull media/video/jellyfin
```

### Ansible Commands

```bash
# Run Ansible for homelab setup
task ansible:apply-homelab

# Run Ansible for cloud setup
task ansible:apply-cloud
```

### Terraform Management

```bash
# Apply Azure VM Terraform configuration
task azure-vm:apply

# Plan Azure VM Terraform changes
task azure-vm:plan

# Destroy Azure VM Terraform resources
task azure-vm:destroy
```

### Utility Commands

```bash
# Show public IP of the server
task get-public-ip

# Show version numbers of installed software
task versions

# Create a compressed backup of the configuration directory
task backup-config

# Download data files for offline use
task get-offline-data
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
- **Pre-commit** for code quality and security checks:
  - Shell script validation with ShellCheck
  - YAML linting and validation
  - Terraform validation and formatting
  - Ansible linting
  - Python linting with Ruff
  - Dockerfile linting with Hadolint
  - Security scanning with Gitleaks and KICS
- **Docker** and Docker Compose for containerized services
- **Python** for service management via the `scripts/labctl.py` tool
- **GitHub Actions** for CI/CD workflows:
  - Pre-commit checks
  - Building devcontainer
  - Building and deploying documentation site
- **Renovate** for automated dependency updates

## Docker Service Management

The repository uses a custom Python script (`scripts/labctl.py`) to manage Docker services defined in YAML files:

1. Services are organized by category (security, media, tools, etc.)
2. Each service has a YAML definition file with container specifications
3. Host-specific configuration is defined in `config/docker/<hostname>/services.yaml`
4. Environment variables are loaded from `.env` files in the config directory
5. The `labctl.py` script supports operations: up, down, restart, recreate, update, pull, config.

When adding or modifying services:
1. Create or edit the YAML file in the appropriate category directory
2. Add the service to the host configuration in `config/docker/<hostname>/services.yaml`
3. Provide any required environment variables in the appropriate `.env` files
4. Deploy using `task docker:apply` or using the specific service command

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
│   ├── monitoring/  # Monitoring services
│   ├── ai/          # AI-related services
│   └── tools/       # Various utility services
├── docs/            # Documentation
├── terraform/       # Terraform configurations
│   └── azure-vm/    # Azure VM deployment with CloudInit
└── scripts/         # Utility scripts
```

When contributing to this repository, follow the pre-commit rules defined in `.pre-commit-config.yaml` which includes linting for shell scripts, Dockerfiles, YAML files, Ansible playbooks, and Terraform configurations.
