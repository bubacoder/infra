# Agent guide

This repository manages self-hosted infrastructure with Terraform, Ansible and
Docker Compose. Shared documentation is the source of truth for humans and agents.

## Essential rules

- Do not create branches, commit or push unless explicitly requested. Preserve
  existing changes and staging.
- Never expose secrets or directly read secret-bearing private inputs. Follow the
  documented safe inspection workflow before working on bootstrap configuration.
- Obtain authorization for live infrastructure actions. Confirm the target and
  original state; never discard recovery data or bypass a safety check to proceed.
- Prefer existing tools and repository patterns; keep changes focused. Inspect
  task definitions before running build, cleanup or operational commands.
- Run relevant offline tests and pre-commit checks; report what was not verified.
- Keep workflow details in the guides below, not here. Document the current
  solution, not session history or implementation-status notes.

## Documentation index

| Topic | Source of truth |
| --- | --- |
| Overview, architecture and repository layout | [README](README.md) |
| Development commands and checks | [Development](README.md#development), [pre-commit configuration](.pre-commit-config.yaml) |
| Bootstrap inputs, secret handling and safe inspection — read before bootstrap work | [Bootstrap inputs and safety](docs/bootstrap-configuration.md) |
| Installation and teardown | [AWS](docs/bootstrap-aws.md), [Proxmox](docs/setup.md), [manual installation](docs/manual-setup.md) |
| Bootstrap DNS and ownership | [Bootstrap DNS](docs/bootstrap-dns.md) |
| Docker service operations and configuration | [Docker services](docker/README.md) |
| Adding services, Compose patterns and environment precedence | [Docker guidelines](docker/guidelines.md) |
| Host configuration and inventories | [Ansible](ansible/README.md) |
| VM provisioning | [Proxmox](vm/proxmox/README.md), [Ubuntu VM methods](vm/proxmox/ubuntu.md) |
| Standalone cloud provisioning | [AWS Terraform](terraform/aws-vm/README.md), [Azure Terraform](terraform/azure-vm/README.md) |
| Access, utilities and maintenance | [Usage](docs/usage.md), [Runbooks](docs/runbooks.md) |
| Backups and restoration | [Backup and recovery](docs/backup.md) |
| Identity and SSO | [Authentik](docs/authentik.md) |

Discover available commands with `task --list-all`; their definitions live in
[Taskfile.yaml](Taskfile.yaml) and its included task files.
