# Getting started on Proxmox

For AWS use [Bootstrap on AWS](bootstrap-aws.md). Both paths provision an Ubuntu
guest using a separate administrative host. The templates select a Docker host with
Traefik and Homepage; [role and service selection](bootstrap-configuration.md#selecting-host-roles-and-applications)
also supports hosts without Docker. Proxmox CLI scripts provision the VM; Ansible
configures and verifies the guest, never the hypervisor.

For Kubernetes, select the [`k3s` bootstrap profile](../ansible/roles/k3s/README.md)
on a dedicated guest instead of the default Docker roles/services.

## Prerequisites

Prepare the [shared Linux controller and Ansible collections](bootstrap-configuration.md#controller-prerequisites),
then verify these Proxmox-specific requirements:

- Controller `rsync` and a matching local SSH key pair.
- A trusted Proxmox SSH alias with noninteractive sudo, `local` snippet storage,
  an unused VM ID/name, storage and bridge.
- DHCP for the guest. Reserve the address externally if a fixed address is required.
- Enough physical free space, healthy thin-pool data/metadata and an acceptable
  memory/storage overcommit policy; automated preflight does not establish capacity.

For selected services, provide a Cloudflare-administered domain, a token with
`Zone:Read`/`DNS:Edit`, ACME email and working deployment-name resolution. An existing
AdGuard may manage exact local names; see [Bootstrap DNS](bootstrap-dns.md).
Proxmox public address records stay externally/DDNS managed.

With `services: []` and DNS disabled, domain/TLS settings, local deployment-name
resolution and service credentials are unnecessary. VM networking and SSH remain required.
For inventory-based installation or other layouts, see [manual installation](manual-setup.md).

## Configure and provision

### Initialize

```bash
task bootstrap:init TARGET=proxmox
```

Pass `TARGET=proxmox` on every target-selecting command. If using a custom
`BOOTSTRAP_CONFIG_DIR=config/<deployment>`, pass it on initialization and every
subsequent command. Always resume using the original deployment directory.

### Edit and inspect configuration

Initialization creates only private `config/bootstrap-proxmox/bootstrap.yaml`
without overwriting existing settings. It does not connect to Proxmox or create a VM.
Edit this one file privately, including its `secrets` section. Native tool inputs
are generated automatically under `generated/` when commands run; never edit them.
Follow [inputs and safety](bootstrap-configuration.md), then review:

- `vm.name`, `vm.username`, key paths and the `proxmox` VM/storage/network settings.
- `proxmox.address: auto` for guest-agent discovery, or an externally reserved IPv4
  address. Ansible requires exactly one IPv4 on the primary NIC.
- The ordered `roles` list and selected `services`, including their
  [conditional settings and credentials](bootstrap-configuration.md#selecting-host-roles-and-applications).
- For services: a published `host.repository_ref` and dedicated deployment
  subdomain. Configure AdGuard only if it already exists; public DNS stays with DDNS.

Set `vm.ssh_public_key` to the original controller `.pub` file (for
example `~/.ssh/id_ed25519.pub`), with its matching `vm.ssh_private_key` path. Do not
copy either key into `config/`. Preflight validates the selected public key;
provisioning transfers it directly to Proxmox. The private key stays on the controller.

Replace required placeholders privately, then inspect only allowlisted settings:

```bash
task bootstrap:show-config TARGET=proxmox
```

### Plan and review

```bash
task bootstrap:plan TARGET=proxmox
```

This is read-only preflight, not a saved provisioning plan. It checks the selected
public key, VM identity conflicts, storage/bridge existence, snippet storage and
configured DNS conflicts. Review the target and VM sizing before approving apply.

### Apply

```bash
task bootstrap:apply TARGET=proxmox
```

Apply checks conflicts again, syncs scripts/public VM inputs, creates and starts
the guest, and waits for cloud-init. It never deletes or replaces an existing VM.
Ansible pins the SSH host key obtained through the trusted guest agent, reconciles
enabled DNS, applies selected roles and deploys selected services. Apply finishes
with acceptance checks.

## Verify acceptance

Run the independent verification command after apply:

```bash
task bootstrap:verify TARGET=proxmox
```

Every deployment checks authenticated access and matching guest facts. Selected
services additionally check controller DNS, trusted HTTPS, persistent certificate/log
paths and stable containers without recreation on repeat Compose deployment.
Homepage also checks its live Traefik widget; `up --wait` alone is not acceptance.
Host-only verification runs no Docker/application checks. Selecting `k3s` adds
API, node and bundled-deployment readiness checks; other custom role workloads
need their own acceptance checks.

Verification never provisions, applies roles, formats storage or rewrites DNS.

## Recovery and updates

After a partial create/apply failure, inspect the VM first. Do not blindly repeat
creation or bypass conflicts. Preserve configuration, SSH trust and DNS receipts.
If the existing guest is still initializing, the bounded readiness helper is:

```bash
task bootstrap:vm-wait TARGET=proxmox
```

After correcting the cause, explicitly approve configuration of that guest:

```bash
task bootstrap:configure TARGET=proxmox
task bootstrap:verify TARGET=proxmox
```

`configure` never provisions a VM. For published repository updates, follow
[revision handling](bootstrap-configuration.md#repository-revisions-and-configuration-updates).

## Cleanup

No automated Proxmox teardown is provided. VM, disk and deployment-owned DNS
disposal require separate approval and provider-side verification. Back up needed
data first; do not delete recovery records while resource or DNS ownership is uncertain.

## Operational limits

- The `vm-*` helpers regenerate `generated/ubuntu-cloud.env` from `bootstrap.yaml` in
  the selected `BOOTSTRAP_CONFIG_DIR` (default `config/bootstrap-proxmox/`). Pass
  the same custom directory to every command and review VM identity before provisioning.
  Provisioning automatically transfers the original `vm.ssh_public_key` to its
  remote staging path.
- DHCP reservations and public DDNS are managed outside bootstrap.
- VM preflight checks that storage and the bridge exist, not thin-pool capacity or
  overcommit policy. Check physical free space and thin-pool health before creating
  a disk.
