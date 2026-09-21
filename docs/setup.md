# Getting Started

The recommended installation path uses one mode-`0600` YAML file and the
bootstrap orchestrator. The current automated scope is intentionally narrow:

- Ubuntu cloud-image VM on Proxmox
- Separate administrative host
- DHCP with an externally managed reservation and local DNS, or a test-only
  operator-managed `/etc/hosts` checkpoint after address discovery
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
- Control of the DHCP server and local DNS resolver for the fully preflighted
  path. For a test-only `network.expected_ipv4: auto` deployment, administrator
  access to the admin host's `/etc/hosts` is sufficient after the VM address is
  discovered.
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
address, and DNS. It prints the resolved VM ID and supplied or deterministic
generated MAC while redacting the Cloudflare token.

The first plan is expected to stop at the external networking checkpoint when
the reservation and DNS records do not exist yet. Use the printed MAC and
`network.expected_ipv4` to:

1. Create the DHCP reservation.
2. Resolve `network.domain` and `*.network.domain` to the reserved address in
   local DNS.
3. Ensure clients use that local DNS resolver.
4. Run `task bootstrap:plan` again until preflight passes.

Bootstrap verifies observable DNS results but does not change the router, DHCP
server, or DNS service.

### Unknown DHCP address (test-only)

Set `network.expected_ipv4: auto` only when a reservation cannot be created
before provisioning. The initial plan validates everything except address and
DNS checks. The first apply creates or resumes the VM, obtains exactly one
non-loopback IPv4 address from the Proxmox guest agent interface matching the
planned MAC, and stops at a networking checkpoint.

Add the reported address to the administrative host's `/etc/hosts` for all of
the names reported by bootstrap, then rerun the same apply command. For the
core profile, these are the base domain, `home`, `traefik`, and
`bootstrap-check` names. Host files have no wildcard support. Bootstrap does
not add mappings automatically or edit `/etc/hosts`, and fails rather than
choosing between multiple guest IPv4 addresses.

Use this explicit, privileged helper instead of editing the file manually:

```bash
task bootstrap:add-hosts NAME=docker-host ADDRESS=192.0.2.10 DOMAIN=example.com
```

For this test-only checkpoint, optionally put your manual entries in this exact
named block, replacing `docker-host` with the VM name:

```text
# BEGIN infra docker-host temporary DNS
192.0.2.10 example.com home.example.com traefik.example.com bootstrap-check.example.com
# END infra docker-host temporary DNS
```

After testing, remove only that block explicitly with `task
bootstrap:cleanup-hosts NAME=docker-host`. Both commands use `sudo`; the add
helper validates its hostname, IPv4 address, and domain and refuses an existing
or malformed block. Cleanup refuses to change `/etc/hosts` if the block is
missing, duplicated, incomplete, or malformed.

## Apply

Start the deployment and approve the displayed target:

```bash
task bootstrap:apply
```

For an already reviewed unattended run, use `task bootstrap:apply YES=1`.

The orchestrator performs these stages:

1. Renders ignored Proxmox, Ansible, and Docker configuration.
2. Creates the VM with the planned MAC, or validates and resumes a matching VM.
3. Waits for the expected DHCP address and successful cloud-init completion.
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
address filter, then stops after guest-agent discovery until the operator has
completed the networking checkpoint described above.

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
