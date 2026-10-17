# Bootstrap Configuration

Version 1 remains the Proxmox configuration described below. Version 2 requires
`target: proxmox` or `target: aws`. Proxmox version 2 uses the same fields as
version 1; AWS uses the separate [AWS example](../config-example/bootstrap-aws.yaml)
and [AWS bootstrap guide](bootstrap-aws.md). Target-specific fields cannot be mixed.

DNS is managed by default during normal bootstrap: optional AdGuard for Proxmox,
Cloudflare address records plus optional AdGuard for AWS. See [Bootstrap DNS](bootstrap-dns.md).
Keep all credentials in the private mode-`0600` configuration.
`network.dns.enabled` defaults to `true`; set it to `false` for manual DNS
management. Resolver verification is still required. Legacy `mode: external`
and `mode: managed` remain supported aliases for disabled/enabled automation;
prefer the boolean and remove `mode` when migrating. Both fields must agree if
supplied together.

`python3 -m scripts.bootstrap` reads `config/bootstrap.yaml` and orchestrates the
supported first-time deployment. The tracked
`config-example/bootstrap.yaml` is the canonical starting point.

## Configuration

```yaml
version: 1

# Optional. If omitted, use the current Git origin URL and branch. The current
# commit must be the selected remote branch tip so the VM can clone it exactly.
repository:
  url: <infrastructure-repository-url>
  branch: bootstrap

deployment:
  # Version 1 supports a separate Ansible administrative host only.
  admin_model: separate

  # Exact service set. Version 1 supports this core pair only.
  services:
    - security/traefik
    - dashboard/homepage

proxmox:
  # SSH destination used for read-only checks and VM provisioning.
  ssh_target: <user@host-or-ssh-alias>

vm:
  # Use a numeric VM ID or "auto" for Proxmox allocation.
  id: <preferred-id-or-auto>
  name: <hostname>
  ubuntu_version: "26.04"
  username: admin
  cpu_cores: 4
  memory_max_mib: 4096
  memory_min_mib: 1024
  disk_size: 256G
  storage: local-lvm
  bridge: vmbr0

  # Optional. A supplied MAC must be valid, unicast, and unused. If omitted,
  # bootstrap derives a stable local MAC from the Proxmox target and VM name.
  mac: <mac-address>

  # Public key installed in the VM and later managed by Ansible.
  ssh_public_key: ~/.ssh/id_ed25519.pub

network:
  # DHCP is the only supported guest-addressing mode. Create a reservation for
  # the planned MAC at this address before applying. For a test-only deployment
  # without a reservation, use "auto" for discovery followed by automated DNS.
  expected_ipv4: <reserved-address-or-auto>

  # Base domain for the wildcard certificate and service routes.
  domain: <public-base-domain>

  dns:
    # Proxmox: local AdGuard only; public address records stay with DDNS.
    # AWS also requires cloudflare.zone (see the AWS example).
    enabled: true
    verify: true
    # Optional; omit if AdGuard does not exist yet. Working DNS is still required.
    # adguard:
    #   url: https://dns-admin.example.com
    #   username: <adguard-web-username>
    #   password: <adguard-web-password>

host:
  docker_volumes: /srv/docker-volumes
  timezone: Etc/UTC

tls:
  provider: cloudflare
  acme_email: <registration-email>

  # Secret value. Bootstrap redacts this from plans, errors, diagnostics, and
  # subprocess arguments.
  token: <cloudflare-dns-api-token>
```

## Secret Handling

The actual file may contain secrets and must meet all of these requirements:

- Store it under the ignored `config/` directory.
- Set mode `0600` before adding a token.
- Commit only placeholder values in `config-example/bootstrap.yaml`.
- Do not pass secrets through command arguments or environment variables.

Bootstrap refuses a group- or world-accessible configuration. Generated secret
files are written atomically with mode `0600`; plans display `<redacted>` rather
than the token.

## Safe inspection for AI agents

Do not give an AI agent the raw private bootstrap YAML. Use:

```bash
# Default config/bootstrap.yaml (typically Proxmox):
task bootstrap:show-config

# A separate AWS configuration:
task bootstrap:show-config CONFIG=config/bootstrap-aws.yaml

# Equivalent without Task:
python3 -m scripts.bootstrap --config config/bootstrap-aws.yaml --show-config
```

The local script reads the file but prints only allowlisted configured settings.
`tls.token` and `network.dns.adguard.password` appear as `<redacted>`. Unknown
fields are omitted, unexpected nested values are hidden, and URLs containing
embedded credentials or query/fragment parameters are redacted. Known secret
values repeated in displayed metadata are also masked. Do not place secrets in
ordinary metadata fields; redaction cannot identify arbitrary mislabeled secrets.

This command is **offline and read-only**: no cloud, DNS, SSH or Git calls, no
rendered files/state, no credential environment inspection, and no provisioning.
It works with placeholders or incomplete settings, without checking SSH-key files,
repository cleanliness, published commits, or provider credentials. Omitted values
are not resolved to defaults. It is an inspection view, **not** proof of a valid
or deployable configuration; use `bootstrap:plan` for authorized live preflight.

The file must still be private (mode `0600` or stricter) under the repository's
ignored `config/` directory and contain parseable YAML with a mapping at its root.
Parse errors show only a safe message and location, never source snippets. If the
command fails, have the operator fix the file privately; an agent must not fall
back to raw file tools or custom content-dumping scripts. Never paste secrets
into chat or command arguments. Output is credential-redacted, **not anonymized**:
it may include account IDs, IPs, domains, usernames and paths. Redact those as
needed before sharing evidence outside the trusted session.

## Address Discovery

The recommended value for `network.expected_ipv4` is the reserved DHCP address.
It lets `bootstrap:plan` check proposed DNS records against the known address.

`auto` is an alternative when the address cannot be reserved first.
Bootstrap creates or resumes the VM, finds the single usable IPv4 address on the
guest-agent interface matching the planned MAC, reconciles local AdGuard entries,
and verifies actual resolution. Ambiguous guest addresses stop deployment.
There is no hosts-file fallback. See [Bootstrap DNS](bootstrap-dns.md) for
provider configuration, external opt-out, safety and cleanup.

## Implementation Map

| Configuration | Generated target or check | Existing consumer |
| --- | --- | --- |
| `repository` | Local revision validation and remote checkout | `git ls-remote`, `git clone` |
| `proxmox.ssh_target` | `PROXMOX_HOST` | `scripts/bootstrap/Taskfile.bootstrap.yaml` |
| `vm.id` | `VMID` | `qm`, `vm/lib-common.sh` |
| `vm.name` | `VMNAME` and ignored inventory hostname | Cloud-init, Ansible, Docker host config |
| `vm.ubuntu_version` | `UBUNTU_VERSION` | `vm/proxmox/create-ubuntu-cloud-vm.sh` |
| VM compute/storage fields | `config/vm/proxmox/ubuntu-cloud.env` | `vm/proxmox/create-ubuntu-cloud-vm.sh` |
| `vm.mac` | `VM_MAC` and Proxmox `net0` | `qm create` in the cloud-image script |
| `vm.ssh_public_key` | Ignored copied public key and inventory key paths | Cloud-init and `debian_base` |
| `network.expected_ipv4` | `EXPECTED_IPV4` and `ansible_host` | Cloud-init wait and `ansible/apply-homelab.sh`; `auto` uses the guest agent after provisioning |
| `network.domain` | Host `MYDOMAIN` | Traefik and Homepage Compose files |
| `network.dns` | Base, service, and wildcard-probe lookups | Python preflight and HTTPS verification |
| `host.docker_volumes` | Ansible host variable and host `DOCKER_VOLUMES` | `debian_docker_host` and Compose |
| `host.timezone` | Host `TIMEZONE` | Traefik and Homepage Compose files |
| `tls.acme_email` | Host `ADMIN_EMAIL` | Traefik ACME configuration |
| `tls.token` | Host `.env.traefik`, mode `0600` | `docker/security/traefik/traefik.yaml` |
| `deployment.services` | Host `services.yaml` | `scripts/labctl.py config apply` |

Generated local files:

```text
config/
├── bootstrap.yaml
├── ansible/inventory/inventory.yaml
├── vm/proxmox/
│   ├── bootstrap-authorized-key.pub
│   └── ubuntu-cloud.env
└── docker/<hostname>/
    ├── .env
    ├── .env.traefik
    └── services.yaml
```

## Process And Entry Points

The Python module keeps orchestration phases explicit and delegates existing
operations rather than reimplementing them:

| Phase | Python function | Existing entry point |
| --- | --- | --- |
| Load and validate | `load_config()` | PyYAML plus local validation |
| Resolve repository, ID, and MAC | `resolve_plan()` | Git and read-only Proxmox commands |
| Validate target and DNS | `preflight()` | SSH, Proxmox storage/bridge, system resolver |
| Render ignored files | `render_config()` | Existing env and inventory contracts |
| Provision or resume VM | `provision_vm()` | `task bootstrap:vm-preflight`, `vm-provision`, `vm-wait` |
| Establish SSH trust | `establish_ssh_trust()` | Proxmox guest agent and `ssh-keyscan` |
| Configure host | `configure_host()` | `ansible/apply-homelab.sh --limit <host>` |
| Prepare services | `prepare_remote_repository()` | Git, `task bootstrap:init-local-config`, rsync |
| Deploy | `deploy_services()` | `task docker:apply` |
| Accept deployment | `verify_services()` | Docker inspection, HTTPS checks, repeat apply |

Public commands:

```bash
task bootstrap:init
task bootstrap:plan
task bootstrap:apply
task bootstrap:apply YES=1
```

`bootstrap:vm-init`, `bootstrap:vm-preflight`, `bootstrap:vm-provision`,
`bootstrap:vm-wait`, and `bootstrap:init-local-config` are advanced/manual
commands for recovery and debugging. Normal users should use `bootstrap:init`,
then `bootstrap:plan`, then `bootstrap:apply`.

The same operations are directly available as:

```bash
python3 -m scripts.bootstrap --config config/bootstrap.yaml --plan
python3 -m scripts.bootstrap --config config/bootstrap.yaml --apply
python3 -m scripts.bootstrap --config config/bootstrap.yaml --apply --yes
```

Rerunning apply is the recovery mechanism. The renderer and Docker apply are
idempotent. Provisioning resumes an existing VM only when its ID, name, MAC,
disks, guest agent, and VM-specific cloud-init snippets match. It never deletes
or replaces a conflicting or partially created resource.
