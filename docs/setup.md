# Getting started on Proxmox

For AWS use [Bootstrap on AWS](bootstrap-aws.md). Both paths deploy an Ubuntu Docker
host with Traefik and Homepage, using a separate administrative host. Provisioning
uses the existing Proxmox CLI scripts; Ansible owns configuration and verification.

## Prerequisites

- A trusted Proxmox SSH alias with noninteractive sudo, `local` snippet storage,
  an available VM ID/name, storage and bridge.
- A matching local SSH key pair. DHCP and working local DNS; an existing AdGuard
  may optionally manage the deployment's exact local names.
- A Cloudflare-administered public domain, DNS token with `Zone:Read`/`DNS:Edit`,
  and ACME email. Proxmox public address records remain externally/DDNS managed.
- On the Linux controller: Git, SSH, rsync, curl,
  [Task](https://taskfile.dev/docs/installation) and Ansible. Install the
  repository collections with `ansible-galaxy collection install -r ansible/requirements.yml`.

Clone and enter the repository; `sudo ansible/bootstrap-ansible.sh` installs
Ansible if needed. See [manual installation](manual-setup.md) for other layouts.

## Configure and provision

```bash
task bootstrap:init TARGET=proxmox
task bootstrap:vm-init
```

No target is selected by default. Pass `TARGET=proxmox` on each target-selecting
bootstrap command; AWS uses the same interface with `TARGET=aws`. To use an existing
custom directory, also pass its `BOOTSTRAP_CONFIG_DIR` on every command. Never
create a fresh backend to resume resources recorded in a different directory.

Edit `config/bootstrap-proxmox/host.yaml`, `secrets.yaml` and
`config/vm/proxmox/ubuntu-cloud.env`. Keep VM name, ID, user and expected address
consistent between the two public tool inputs. Set the published repository branch,
tag or commit and deployment subdomain. Public DNS stays with DDNS; configure AdGuard
only if it already exists. See [inputs and secrets](bootstrap-configuration.md).

Supply the exact public key instead of assuming the hypervisor's authorized keys
are the same as the controller's:

```bash
cp ~/.ssh/id_ed25519.pub config/vm/proxmox/bootstrap-authorized-key.pub
```

Set `SSH_PUBLIC_KEY_FILE=/tmp/vm/proxmox/bootstrap-authorized-key.pub` in the VM
environment file. Use the corresponding key paths in `host.yaml`.

```bash
task bootstrap:plan TARGET=proxmox
task bootstrap:apply TARGET=proxmox
```

Repository configuration accepts a fixed SHA or a branch that follows its remote
tip. See [repository revisions and configuration updates](bootstrap-configuration.md#repository-revisions-and-configuration-updates)
to update code on an existing VM without reprovisioning it.

The VM tasks check conflicts, sync the existing scripts/public VM inputs, create
and start the guest, and wait for cloud-init. They do not delete or replace an
existing VM. Reserve its DHCP lease externally, or set `proxmox_address: auto` for
guest-agent discovery. Ansible requires exactly one IPv4 address on the VM's
primary NIC and pins the SSH host key obtained through the trusted guest agent.

## Configure, verify and recover

Ansible optionally creates exact AdGuard rewrites, checks the controller's actual
DNS answers, applies the existing Debian/Docker roles to only this guest, checks
out the selected repository revision, templates private service settings and runs
Compose.
It verifies trusted HTTPS for Homepage and Traefik, the live Homepage widget,
persistent certificate/log paths, stable containers and repeat Compose deployment
without recreation. `up --wait` alone is not the application acceptance check.

For a provisioned guest, correct the reported cause, then explicitly approve:

```bash
task bootstrap:configure TARGET=proxmox
task bootstrap:verify TARGET=proxmox
```

`configure` never provisions a VM. `verify` does not format storage or rewrite DNS,
but deliberately repeats Compose as an acceptance test. After a partial VM-create
failure inspect Proxmox first; do not blindly rerun creation or bypass conflicts.
No automated Proxmox teardown is provided. Disposal of VMs, disks or owned DNS
requires separate approval and provider-side verification.

## Operational limits

- The `vm-*` helpers use the single file `config/vm/proxmox/ubuntu-cloud.env`.
  Review its VM identity and settings before provisioning; `BOOTSTRAP_CONFIG_DIR`
  selects host/service inputs, not a different VM environment file.
- DHCP reservations and public DDNS are managed outside bootstrap.
- VM preflight checks that storage and the bridge exist, not thin-pool capacity or
  overcommit policy. Check physical free space and thin-pool health before creating
  a disk.
