# Ansible

[Ansible Collaborative](https://www.ansible.com/)

> Automation for everyone
> No matter your role, or what your automation goals are, Ansible can help you demonstrate value, connect teams, and deliver efficiencies for your organization.
> Built on open source, Red Hat® Ansible® Automation Platform is a hardened, tested subscription product that offers full life cycle support for organizations. Explore how Ansible can help you automate today—and scale for the future.

## Tutorials, Resources

- [Learn Linux TV - Getting started with Ansible](https://www.youtube.com/playlist?list=PLT98CRl2KxKEUHie1m24-wkyHpEsa4Y70)
- [Laying out roles, inventories and playbooks](https://leucos.github.io/ansible-files-layout)
- [An evolving set of mac user creation, setup and maintenance playbooks being used at Ideas On Purpose](https://github.com/ideasonpurpose/ansible-playbooks)
- [Variable precedence: Where should I put a variable?](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html#variable-precedence-where-should-i-put-a-variable)

## Directory structure

- `ansible` -- Configuration of the host OS & required software
  - `ansible/roles` -- Roles for Debian-based Docker & admin hosts and a Mac-based DevOps/SRE toolset
  - `ansible/playbooks` -- Host-role assignments. The playbooks can be executed with the `apply-*.sh` scripts
  - `ansible/inventory` -- Host specific environment configuration

## Setup steps

1. From the repository root, install Ansible on the selected admin environment with `sudo ansible/bootstrap-ansible.sh`. This can be the Docker host in single-host mode. (See: [Ansible control node](https://docs.ansible.com/ansible/latest/network/getting_started/basic_concepts.html#control-node))
2. Copy `config-example/ansible` to the ignored `config/ansible` overlay and configure its inventory and secret variables.
3. Add hosts to `config/ansible/inventory/inventory.yaml`.
4. Assign roles by adding hosts to the corresponding inventory groups, such as `docker_hosts`.
5. Run `ansible/apply-<playbook>.sh` from the repository root to execute a playbook.
   - If you use a non-root user and `sudo` requires a password (indicated by the "Missing sudo password" error message), use `ansible/apply-<playbook>.sh --ask-become-pass` and specify the password when requested ("BECOME password" message)
   - The playbook will set up passwordless `sudo`, so next time the `--ask-become-pass` parameter will not be required
6. When the administrative user is already created, use that user in the inventory instead of `root` (`ansible_user: <adminuser>`). This is more secure and also required by Homebrew.

Task wrappers are available from the repository root:

```bash
task ansible:apply-localhost
task ansible:apply-homelab
task ansible:apply-cloud
```

These apply host configuration. Inspect the inventory and obtain authorization
before running them. To limit a run to one host or supply Ansible options, use the
`apply-*.sh` scripts directly, for example `ansible/apply-homelab.sh --limit <host>`.

For complete automated installation, choose the [AWS](../docs/bootstrap-aws.md) or
[Proxmox](../docs/setup.md) guide. For manual inventory-based installation, see
[Manual installation](../docs/manual-setup.md).

The [`k3s` role](roles/k3s/README.md) provides an opt-in default single-server
Kubernetes profile for either bootstrap target, including read-only verification.
The separate [`k3s_cilium` role](roles/k3s_cilium/README.md) prepares opt-in
networking before `k3s`; bootstrap verifies its rollouts after the server starts.
The optional [`k3s_traefik` role](roles/k3s_traefik/README.md) configures bundled
ingress with shared file middleware and persistent ACME, without duplicating
application Compose definitions or installing a second Traefik.

## Host resolver handling

`debian_base` sets `DNSStubListener=no` in the `[Resolve]` section when
`/etc/systemd/resolved.conf` exists. The section-aware INI task inserts a missing
option and notifies a resolver restart independently of `/etc/resolv.conf`
changes. Existing unrelated resolver settings are preserved. Hosts without that
main configuration file are skipped; systemd drop-in overrides still require
review. This host configuration is separate from Kubernetes ServiceLB DNS
publication; loopback port-53 listeners alone do not establish a LAN-IP conflict.

## Bootstrapping hosts with authentication

1. Copy public SSH key, e.g.:
   `ssh-copy-id -i ~/.ssh/id_ed25519.pub root@192.168.1.50`
2. Run playbook with existing user (`root` or your admin user if already created)
3. From the repository root, verify one host with both inventory sources:
   `ansible <host> -m ping -i ansible/inventory/inventory.yaml -i config/ansible/inventory/inventory.yaml`

## Third-party APT packages

Use `debian_tools_apt_repositories` to opt hosts into signed repository/package
combinations. See the [APT repository role](roles/apt_repositories/README.md) for
the schema, Azure CLI selection and disable semantics. Docker also reuses this
role, retaining its own version pins, holds and service setup. CrowdSec keeps its
specialized installation path because it must suppress package-triggered service
startup until credentials and firewall prerequisites are ready. The Ansible
bootstrap script runs before roles are available and is intentionally separate.

## Homebrew package types and trust

Formulae and casks have separate package lists and installation tasks. TFLint is
a third-party cask with Linux and macOS artifacts; on Linux it is selected by the
Terraform tools group through `debian_tools_brew_cask_packages_terraform`. Other
explicit Linux-compatible casks can be set in `debian_tools_brew_cask_packages`.
macOS uses `mac_base_brew_cask_packages`, including Azure CLI and TFLint.

Both roles derive taps and item-level trust from fully qualified names in their
configured lists. Formulae receive formula trust and casks receive cask trust;
no entire third-party tap is implicitly trusted. Trust is established before
Ansible's package metadata queries.

Devcontainer APT cache IDs include the base image and target architecture.
`sharing=locked` serializes access, but cannot by itself prevent one
distribution's `apt-get update` from replacing another's package metadata.
The tools role also refreshes missing or stale metadata before installing base
packages: restoring an image layer does not necessarily restore its cache mounts.

## Useful options

The following parameters can be applied to `ansible-playbook` and the "apply..." scripts.

- `-l`, `--limit` - Limit Ansible run for a specific host (or host group). Example: `./apply-homelab.sh --limit <host>`
- `-v`, `--verbose` - Causes Ansible to print more debug messages. Adding multiple -v will increase the verbosity, the builtin plugins currently evaluate up to -vvvvvv. A reasonable level to start is -vvv, connection debugging might require -vvvv. Example: `./apply-homelab.sh -v`

See `man ansible-playbook` for more.

## GUI

[GitHub - ansible/awx: AWX provides a web-based user interface, REST API, and task engine built on top of Ansible. It is one of the upstream projects for Red Hat Ansible Automation Platform.](https://github.com/ansible/awx)
