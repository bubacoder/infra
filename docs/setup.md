# Getting started on Proxmox

For AWS use [Bootstrap on AWS](bootstrap-aws.md). Both paths provision an Ubuntu
guest using a separate administrative host. The templates select a Docker host with
Traefik and Homepage; [role and service selection](bootstrap-configuration.md#selecting-host-roles-and-applications)
also supports hosts without Docker. Proxmox CLI scripts provision the VM; Ansible
configures and verifies the guest, never the hypervisor.

For Kubernetes, select the [`k3s` bootstrap profile](../ansible/roles/k3s/README.md)
on a dedicated guest instead of the default Docker roles/services.
For opt-in Cilium instead of Flannel, see [Cilium networking](../ansible/roles/k3s/README.md#optional-cilium-networking)
and enable it before the first apply.
For optional direct API access and a controller-side kubeconfig/context, follow
the [K3s access profile](../ansible/roles/k3s/README.md#access-and-lifecycle).

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
# Dedicated Kubernetes guest instead of the default Docker profile:
task bootstrap:init TARGET=proxmox PROFILE=k3s BOOTSTRAP_CONFIG_DIR=config/my-k3s
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

For a non-mutating progress snapshot while apply runs, use
`task bootstrap:status TARGET=proxmox` (add the same
`BOOTSTRAP_CONFIG_DIR=config/<deployment>` when applicable). It reports whether
the VM and guest agent are running, cloud-init has finished and, after the pinned
SSH key exists, whether K3s is active and its node Ready. It does not replace
independent acceptance verification.

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

Cloud-init installs and starts the guest agent before performing the full OS
upgrade, so progress remains observable during lengthy upgrades. Readiness has
two independent bounded waits, configurable in the private `proxmox` section:

```yaml
proxmox:
  # Retain all existing VM/provider settings.
  agent_timeout_seconds: 600
  cloud_init_timeout_seconds: 1800
```

Each timeout is an integer from 1 to 86400 seconds; existing sources without these
fields use the shown defaults. The cloud-init budget starts **after** the agent
and expected address are available, rather than consuming the agent's remaining
time. The same settings apply to provisioning, `vm-wait` and configuration.
Cloud-init success is still required before configuration or SSH trust pinning;
an available agent alone is not acceptance. OS upgrade failures fail cloud-init.

After a partial create/apply failure, inspect the VM first. Do not blindly repeat
creation or bypass conflicts. Preserve configuration, SSH trust and DNS receipts.
Use `bootstrap:status` with the original target/directory to distinguish an absent
or stopped VM, pending agent/network, active cloud-init and completed initialization.
An agent timeout is not proof of a boot failure. Cloud-init errors need private
diagnosis; do not restart, delete or replace the guest merely to clear a timeout.
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

Use the same reviewed bootstrap commands for Proxmox and AWS, always with the
original private deployment directory. Back up needed data before destruction:

```bash
task bootstrap:destroy-plan TARGET=proxmox BOOTSTRAP_CONFIG_DIR=config/my-deployment DELETE_DATA=1
task bootstrap:destroy TARGET=proxmox BOOTSTRAP_CONFIG_DIR=config/my-deployment
```

The plan checks native Proxmox VM identity, disk and cloud-init snippet ownership,
guest state, configured storage, snapshots and backups. It refuses ambiguous or
protected resources, snapshots, backups, and foreign/unreferenced disks. DNS
ownership is previewed without writes. Review the saved private plan and the
summarized scope before confirming destruction. The second command requires
unchanged inputs and plan bytes, shuts down the guest gracefully (no forced stop),
rechecks identity, destroys the VM and its referenced disks, then verifies absence.
Only the two plan-owned VM-specific cloud-init snippets and DNS receipt-owned
records are removed; no shared snippets, backups or snapshots are deleted.
Keep original DNS provider settings and credentials available until owned records
have been removed; disabling DNS while records remain blocks the reviewed plan.
Receipt-owned local Kubernetes credentials are removed without touching unrelated
contexts. Private `bootstrap.yaml`, generated input, reviewed plan and ownership
receipts remain for recovery; do not remove them to bypass a failed check.

If verification or DNS/local cleanup fails **after** VM destruction, retain the
original directory and retry without destroying again:

```bash
task bootstrap:destroy-cleanup TARGET=proxmox BOOTSTRAP_CONFIG_DIR=config/my-deployment
```

Changed inputs or an absent reviewed plan must be investigated, not replaced with
a fresh plan for a deleted VM. Externally managed DHCP reservations, public DNS
and backups require their own separately reviewed cleanup.

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
