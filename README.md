# Home Infra<!-- omit in toc -->

![GitHub License](https://img.shields.io/github/license/bubacoder/infra)
![Docs-web workflow](https://img.shields.io/github/actions/workflow/status/bubacoder/infra/docs-web.yml?label=docs)
![Dev Container workflow](https://img.shields.io/github/actions/workflow/status/bubacoder/infra/devcontainer.yml?label=devcontainer)
![Pre-commit checks workflow](https://img.shields.io/github/actions/workflow/status/bubacoder/infra/pre-commit.yml?label=checks)

This repository contains the Infrastructure as Code (IaC) configuration and documentation for my home infrastructure. The main goals of this ever-evolving setup are:
- Create a local, self-hosted environment for various services and applications, minimizing reliance on external cloud providers.
- Learning and organizing knowledge, best practices, and tool documentation into a single repository.

## Table of Contents<!-- omit in toc -->

- [Principles](#principles)
- [Key Software Components \& Services](#key-software-components--services)
  - [Local Infrastructure Components](#local-infrastructure-components)
  - [Cloud Services (External Dependencies)](#cloud-services-external-dependencies)
- [Getting Started](#getting-started)
- [Development](#development)
  - [GitHub automations](#github-automations)
- [EOL](#eol)

## Principles

- **Automate Everything**: Embrace the "cattle, not pets" approach by automating as much as possible to ensure consistency and reproducibility.
- **Prioritize Local Functionality**: While cloud services may be utilized, the focus is on minimizing external dependencies and enabling local, cloud-independent functionality.
- **Minimal and Energy-efficient Hardware**: Favor energy-efficient hardware solutions to reduce environmental impact and operational costs.
- **Avoid Overcomplication**: Maintain a lightweight and straightforward setup by avoiding unnecessary complexities.
- **Extensibility and Easy Configuration**: Ensure that the infrastructure is easily extensible and configurable to accommodate future changes and requirements.
- **Security-minded**: Prioritize security best practices and implement appropriate measures to protect the infrastructure and data.

## Key Software Components & Services

The key components of this infrastructure include:

### Local Infrastructure Components

- **Proxmox Virtual Environment**: A Type 1 hypervisor for managing virtual machines and containers.
- **Ubuntu Server**: The host OS for running Docker containers and administrative tools.
- **Ansible**: Used for configuring the host OS and deploying required software.
- **Docker Compose**: For defining and managing Docker container configurations.
- **Traefik**: A reverse proxy with TLS certificate management.
- **Authelia**: Provides authentication and single sign-on capabilities.
- **Guacamole**: A web-based remote desktop and SSH access solution.
- **Homepage**: A dashboard for managing and accessing various services.

### Cloud Services (External Dependencies)

The long-term goal is to reduce these dependencies and provide offline alternatives.

| Name                                                                     | Description                            | Remarks                                                                 |
| ------------------------------------------------------------------------ | -------------------------------------- | ----------------------------------------------------------------------- |
| Docker images                                                            | All services are running as containers | Downloaded on first use                                                 |
| Plugins, Modules (e.g. Crowdsec)                                         | Various plugins for services           | Downloaded on first use. TODO create inventory                          |
| Large Language Models                                                    | Optional, used by Ollama               | Downloaded on first use                                                 |
| [OVHcloud](https://www.ovhcloud.com/en/) (or other registrar)            | Domain Name registration               | Required for remote access and TLS certificates. TODO document fallback |
| [Cloudflare](https://www.cloudflare.com/)                                | DNS zone administration, tunnel        | Optional, for remote access                                             |
| [Let's Encrypt](https://letsencrypt.org/)                                | TLS certificates (managed by Traefik)  | Required. TODO document local CA setup for fallback                     |
| [Backblaze B2](https://www.backblaze.com/cloud-storage)                  | Backup storage                         | Optional, local backup also configured                                  |
| [CrowdSec](https://app.crowdsec.net/)                                    | Crowd-sourced IP blocklist             | Optional, security service, can be disabled                             |
| [Azure](https://azure.microsoft.com/)                                    | Temporal VM, storage                   | Optional, not used by any lab components                                |
| [Homepage Icons](https://github.com/walkxcode/dashboard-icons/tree/main) | Icon set for the services              | Optional, hosted on a CDN. TODO host locally                            |

## Getting Started

The recommended configuration is to setup Proxmox VE and install a Debian- or Ubuntu-based VM to host the Docker services.

-> See [Getting Started](docs/setup.md)

## Development

All development dependencies are available in the devcontainer or can be set up with an Ansible role.

Some development workflows:

Code quality scanning tools are set up via [pre-commit](https://pre-commit.com).
Perform the checks by running `task lint` (or `pre-commit run --all-files`).

Create/update example `.env` files: `task docker:create-example-env`.

### GitHub automations

- Workflows configured (see in [`.github/workflows`](.github/workflows)):
  - [Pre-commit checks](.github/workflows/pre-commit.yml)
  - [Build dev & admin container](.github/workflows/devcontainer.yml)
  - [Build and deploy documentation site](.github/workflows/docs-web.yml)
- Updating the container images and other components is automated with [Renovate](https://docs.renovatebot.com/)
  - [GitHub Marketplace App](https://github.com/marketplace/renovate)
  - Configured with [`renovate.json`](renovate.json)
  - Free for public and private repositories
- AI Code Review for MRs is done with [Code Rabbit](https://www.coderabbit.ai/)
  - [GitHub Marketplace App](https://github.com/marketplace/coderabbitai)
  - Configured with [`.coderabbit.yaml`](.coderabbit.yaml)
  - Free for public repositories

## EOL

> A crowd-sourced guide to help techs help their non-tech spouses / partners / parents / kids when we are at the end-of-life.

[End-of-life Disaster Response](https://github.com/potatoqualitee/eol-dr?tab=readme-ov-file)
