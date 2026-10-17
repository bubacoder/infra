# Getting Started

Choose the target: the guide below covers **Proxmox**. For the alternative AWS
EC2 bootstrap workflow, see [Bootstrap on AWS](bootstrap-aws.md).

The recommended installation path uses one mode-`0600` YAML file and the
bootstrap orchestrator. The current automated scope is intentionally narrow:

- Ubuntu cloud-image VM on Proxmox
- Separate administrative host
- DHCP with an externally managed reservation, or guest-agent address discovery
- Optional automated local DNS through AdGuard Home; public address records stay with DDNS
- Local ignored configuration on the Docker host
- Cloudflare DNS-01 certificates
- Traefik and Homepage

Use the [manual installation](manual-setup.md) for unsupported layouts or to
run and debug individual stages.

## Prerequisites

Before starting, prepare:

- A Proxmox SSH account with noninteractive `sudo` access to `qm`, storage, and
  VM configuration.
- Proxmox storage named `local` with snippet content enabled.
- An unused VM name and either a preferred VM ID or automatic allocation.
- A public SSH key and its corresponding private key or SSH-agent identity.
- Control of the DHCP server when using a reservation, plus working local DNS.
  If AdGuard already exists, optionally supply its API endpoint and web credentials
  to automate local DNS. Otherwise arrange DNS externally; AdGuard is not a prerequisite.
  With `network.expected_ipv4: auto`,
  bootstrap discovers the guest address and creates DNS rewrites during apply.
- A public domain administered through Cloudflare.
- A Cloudflare token with `Zone:Read` and `DNS:Edit` for that domain.
- Git, Python 3, PyYAML, SSH, rsync, Ansible, curl, and
  [Task](https://taskfile.dev/docs/installation) on the administrative host.

Clone and enter the infrastructure repository. The selected branch must be
pushed: bootstrap verifies that the local commit is exactly the remote branch
tip so the Docker host can clone the same code.

```bash
git clone <infrastructure-repository-url> ~/repos/infra
cd ~/repos/infra
sudo ansible/bootstrap-ansible.sh
```

## Configure

Create the ignored bootstrap configuration and restrict its permissions before
adding the Cloudflare token:

```bash
task bootstrap:init
```

Edit `config/bootstrap.yaml`. If `repository` is omitted, bootstrap uses the
current checkout's `origin` URL and branch. See
[Bootstrap Configuration](bootstrap-configuration.md) for every field and its
generated destination.

The real file may contain secrets. Never commit it, paste it into command-line
arguments, or relax its permissions. Bootstrap redacts the token from plans and
errors and writes the generated Traefik file with mode `0600`.

## Plan

Run the non-destructive plan:

```bash
task bootstrap:plan
```

The plan validates the schema, repository revision, local tools, Proxmox SSH
and sudo, VM ID/name/MAC availability, storage, bridge, SSH public key, expected
address, and proposed AdGuard DNS changes. It prints the resolved VM ID and supplied or deterministic
generated MAC while redacting the Cloudflare token.

Use the printed MAC and `network.expected_ipv4` to create a DHCP reservation,
unless using `auto`. Ensure clients use your AdGuard resolver. Bootstrap does
not change router or DHCP settings.

DNS automation defaults to `network.dns.enabled: true`. Set it to `false` for
external DNS management while retaining resolution checks. Optionally configure
`network.dns.adguard` as described in
[Bootstrap DNS](bootstrap-dns.md). Plan reads the API and refuses conflicting
entries without changing DNS; apply creates exact deployment-name rewrites and
verifies the administrative host's DNS answers. Proxmox never creates Cloudflare
address records: existing DDNS continues to manage public DNS. The Cloudflare
token is still required for certificate challenges.

Without AdGuard configured, no Proxmox DNS writes are made. Required names must
still resolve to the VM's LAN IP through an externally supplied resolver;
bootstrap stops if they do not. DDNS public answers alone may not meet that check.

### Unknown DHCP address

Set `network.expected_ipv4: auto` to discover exactly one non-loopback IPv4
address through the Proxmox guest agent interface matching the planned MAC.
Plan checks provider access and name conflicts without knowing the future IP.
Apply discovers the address, creates AdGuard entries, and verifies resolution
before proceeding. Ambiguous addresses stop deployment. Hosts-file helpers and
fallbacks are no longer supported; existing hosts files are never modified.

## Apply

Start the deployment and approve the displayed target:

```bash
task bootstrap:apply
```

For an already reviewed unattended run, use `task bootstrap:apply YES=1`.

The orchestrator performs these stages:

1. Renders ignored Proxmox, Ansible, and Docker configuration.
2. Creates the VM with the planned MAC, or validates and resumes a matching VM.
3. Waits for the DHCP address and successful cloud-init completion, reconciles
   AdGuard DNS, and waits up to 60 seconds for correct local resolution.
4. Compares the network SSH host key with the key obtained through the trusted
   Proxmox guest agent before accepting it.
5. Runs Ansible with a strict limit for only the new host.
6. Clones the same repository branch and commit on the Docker host.
7. Initializes local Docker configuration and transfers generated mode-`0600`
   service secrets without placing them in command arguments.
8. Checks Docker networking, deploys the configured services, and waits for
   stable containers and trusted HTTPS routes.
9. Repeats the Docker deployment and verifies that it does not recreate the
   running core containers.

With `network.expected_ipv4: auto`, stage 3 waits for cloud-init without an
address filter before guest-agent discovery and DNS reconciliation.

The process never deletes an existing VM, disk, or persistent service data.

## Resume And Troubleshoot

After correcting a reported problem, rerun the same apply command. Rendering
and service deployment are idempotent; an existing VM is resumed only when its
ID, name, MAC, disks, guest agent, and VM-specific cloud-init snippets match the
plan. A conflicting or partially created resource stops the process for manual
inspection.

The commands below are advanced/manual recovery and debugging commands. Normal
users should use `task bootstrap:init`, then `task bootstrap:plan`, then `task
bootstrap:apply`.

```bash
task bootstrap:vm-preflight
task bootstrap:vm-wait
task docker:check-host
task docker:apply
```

For individual commands, alternate installation methods, and detailed recovery,
use the [manual installation](manual-setup.md), [Ubuntu VM guide](../vm/proxmox/ubuntu.md),
and [runbooks](runbooks.md).
