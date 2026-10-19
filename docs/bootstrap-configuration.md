# Bootstrap inputs and safety

Bootstrap delegates infrastructure to Terraform, guest configuration to Ansible,
and container lifecycle to Compose. A small Python configuration compiler prepares
their inputs; Task sequences the native commands. Python does not own infrastructure
state, DNS ownership, SSH trust or storage initialization.

This guide is the shared reference for operators and agents. For the complete
installation and teardown procedures, choose the [AWS guide](bootstrap-aws.md) or
[Proxmox guide](setup.md). Provider settings and DNS ownership are covered in
[Bootstrap DNS](bootstrap-dns.md).

## One private operator input

The compiler needs Python 3.11+ and PyYAML in the controller's `python3` environment.
On Ubuntu, install missing YAML support with `sudo apt install python3-yaml`;
check it with `python3 -c 'import yaml'`. No additional Python orchestration
framework is needed.

Every target-selecting bootstrap command requires `TARGET=aws` or `TARGET=proxmox`.
Neither is a default. Missing, empty or invalid targets fail before commands run.

Choose either installation:

```bash
task bootstrap:init TARGET=aws
task bootstrap:init TARGET=proxmox
```

Defaults are isolated: AWS uses `config/bootstrap-aws/`, Proxmox uses
`config/bootstrap-proxmox/`. Initialization creates only `bootstrap.yaml`, without
overwriting operator edits. Start with the tracked templates:
[Proxmox](../config-example/bootstrap-proxmox.yaml) or
[AWS](../config-example/bootstrap-aws.yaml).

If `bootstrap.yaml` is missing, initialization requires an empty deployment
directory. Restore the original source when recovering an existing deployment;
never discard its state or recovery records to make initialization proceed.

Define VM name, user and SSH key paths once under `vm`. Set host/application
settings under `host`, provider inputs under `proxmox` or `aws`, DNS settings under
`dns`, Cloudflare/optional AdGuard credentials under `secrets`, and ordered host
roles and applications under the explicit `roles` and `services` lists.
The schema rejects unknown fields, duplicate YAML keys and mismatched targets.
Native Terraform/Ansible validation still applies after conversion.

Every operational command prepares the needed native inputs automatically:

| Generated file | Consumer | Contents |
| --- | --- | --- |
| `generated/host.yaml` | Ansible | Non-secret host, DNS and application settings |
| `generated/secrets.yaml` | Ansible only | Service credentials, never Terraform inputs |
| `generated/aws.tfvars.json` | Terraform, AWS only | Infrastructure inputs and public SSH key |
| `generated/ubuntu-cloud.env` | Proxmox scripts only | VM inputs derived from the same identity |

Never edit generated files: they are machine-owned and replaced on subsequent
commands. Keep the source and generated files private (`0600`) and their deployment
and generated directories `0700`. Unsafe permissions and symlinked inputs/artifact
directories are rejected. State, plans and recovery files remain in the original
deployment directory, not `generated/`; regeneration never deletes them.

Keep SSH keys in their original controller location and reference their paths under
`vm`. Provisioning transfers only the public key directly to Proxmox. No private
key is read by the compiler. Initialization does not connect to Proxmox or create a VM.

AWS initialization fills exact account/CIDR template placeholders using the active
AWS identity and `https://api4.ipify.org`, validating the selected public key before
writing detected defaults. Review them before planning. Configured account/CIDR
values are never refreshed. Public key material is read from `vm.ssh_public_key`
when Terraform inputs are generated, rather than duplicated in the source.
Detection failures preserve placeholders; correct the cause and rerun init.
Use `BOOTSTRAP_SSH_PUBLIC_KEY=~/.ssh/<key>.pub` when initializing a new source to
select another key pair. Existing source key settings are not overwritten.

The entire `bootstrap.yaml` is secret-bearing, including when most fields look
public. Edit it privately; never share it with an agent. Vault-encrypted input is
not supported. Native Ansible loads/renders generated credentials with `no_log: true`.
Never put credentials in Terraform variables, command arguments or logs. Do not
use `--diff` or debug secret variables.

Use `BOOTSTRAP_CONFIG_DIR=config/<directory>` to select a different deployment input/state
directory. Keep it under the ignored `config/` directory. Use one directory per
deployment; do not reuse an initialized backend for a different account/host.
Pass the same explicit `TARGET` and custom directory on every command. A mismatch
between `TARGET` and `bootstrap.yaml` is rejected, including during reinitialization.
Always use the deployment's existing backend when managing provisioned resources;
never substitute a fresh empty state directory.
AWS credentials use the normal credential chain (for example an explicitly
selected `AWS_PROFILE`); credentials are never copied to the guest.

`host.repository_ref` accepts a published branch, tag or full commit SHA.
Terraform validates infrastructure inputs; Ansible's native argument specification
validates host/service inputs.

## Selecting host roles and applications

Both target templates explicitly select the existing Docker host setup:

```yaml
roles:
  - debian_base
  - debian_docker_host
services:
  - security/traefik
  - dashboard/homepage
```

Roles execute in list order using native Ansible role inclusion. Names must be
unique local directories under `ansible/roles/`, with a `tasks/main.yaml` or
`tasks/main.yml` entry point. Paths, collection names, missing roles and duplicates
are rejected before provider access. Select roles suitable for the Ubuntu guest;
role dependencies and role-specific prerequisites still follow native Ansible behavior.
Adding a future local role makes it selectable without a compiler allowlist change;
this repository does not yet include a k3s role or k3s acceptance checks.

For a host without Docker or bootstrap-managed applications, retain the VM/provider
sections and replace these configuration sections:

```yaml
roles:
  - debian_base
services: []
host: {}
dns:
  enabled: false
secrets: {}
```

An empty role list is also allowed for a provisioned guest with no role-based
configuration. `debian_base` is not silently inserted. Removing a role or service
from the lists does **not** uninstall software, stop existing containers, or delete
data/DNS. Such lifecycle changes require separately reviewed operations.

Currently supported services are `security/traefik` and `dashboard/homepage`.
Any nonempty service list requires `debian_docker_host`; Homepage also requires
Traefik for its bootstrap routing/widget profile. Traefik alone is supported.
The guest's generated service-management profile contains only selected services.

Settings are required only by enabled features:

| Feature | Required settings |
| --- | --- |
| Any bootstrap service | All `host` fields from the template and `secrets.cloudflare_token` for TLS |
| Docker role, even with no services | `host.docker_volumes`; AWS bind mounts must remain below `/storage/` |
| Enabled DNS management | `host.domain`; AWS also needs `dns.cloudflare_zone` and `secrets.cloudflare_token` |
| Enabled DNS with existing AdGuard endpoints | `secrets.adguard_username` and `secrets.adguard_password` |
| No services and DNS disabled | No domain, ACME email, repository settings, or service credentials required |

Host-only acceptance checks authenticated access, matching guest facts and, on AWS,
the verified persistent storage mount. It runs no Docker, Compose, widget or HTTPS
application tests. With services selected, acceptance checks only their routes,
persistent data and containers. `bootstrap:verify` never applies roles, even when
the role list is nonempty. It does not imply application-specific readiness for
future roles such as k3s.

## Repository revisions and configuration updates

For example, `repository_ref: main` or `repository_ref: feature/bootstrap` under `host` is valid.
Ansible passes this value directly to its native Git module during configuration:
a full SHA checks out that exact commit; a branch follows its current remote tip.
Git reports unavailable refs when checking out the guest repository, not during
infrastructure planning.

To deploy a published branch update, rerun
`task bootstrap:configure TARGET=aws` or `TARGET=proxmox` with the same directory.
The existing host picks up the branch update without reprovisioning. With a SHA,
update `repository_ref` to the new commit first. Local guest edits are preserved
(`force: false`). Infrastructure or cloud-init changes still require their own
reviewed plan; configure does not apply Terraform or rerun cloud-init.

## Safe configuration inspection

```bash
task bootstrap:show-config TARGET=aws
task bootstrap:show-config TARGET=proxmox
task bootstrap:show-config TARGET=aws BOOTSTRAP_CONFIG_DIR=config/my-test
```

For agents, these commands are the only supported configuration inspection
interface. Do not read `bootstrap.yaml`, generated credentials, Terraform state or other secret-bearing
inputs with file tools, `cat`, `grep` or ad-hoc scripts. Operators enter secrets
privately; never copy them into chat, command arguments, logs or Terraform inputs.

The offline compiler reads the private source internally and prints only explicitly
allowlisted non-secret settings. It does not generate files, read Terraform state,
read private SSH keys or contact providers. Parser failures never display private
values. This is not a general-purpose secret scrubber: put credentials only under
`secrets`. Output is not anonymized: redact identifiers before sharing outside the trusted session.
On failure have the operator correct the file privately; never fall back to raw
secret-file reads. Use `bootstrap:plan` separately for authorized live preflight.

## State and ownership

AWS runs the canonical `terraform/aws-vm` root directly with an isolated local
backend at `<selected-directory>/aws.tfstate` and provider cache in `.terraform/` beside
it. Saved plans are also private. Terraform owns resource identity, dependencies,
locking, refresh and destruction. Do not use standalone `aws-vm:*` tasks against
this backend. Review native plans: missing resources can be recreated by Terraform
and changed provisioning inputs can propose replacement. Never apply an unreviewed
replacement plan.

Successful AWS planning also saves a private input/plan fingerprint beside the plan.
Apply/destruction requires both the prepared inputs and saved plan bytes to match
that record. Configuration changes, public-key changes or plan changes require a new
reviewed plan. A failed planning run invalidates the previous fingerprint. Do not
run concurrent bootstrap commands or edit the source during a command.

Live planning, provisioning, configuration and destruction require operator
authorization. Do not modify private inputs or deployment state without approval.
Never discard state, import resources or provision replacements to bypass a
conflict; stop and report the cause instead.

Ansible uses an in-memory inventory for only the selected guest; no shared inventory
is edited. Generated Compose files and service secrets are written directly on the
guest. The controller retains a dedicated `known_hosts`, a small DNS ownership
receipt and first-format attempt markers. These records protect SSH trust, DNS
ownership and storage initialization.

## Target-aware commands

Use `init`, `show-config`, `plan`, `apply`, `configure` and `verify` with either
explicit target. `plan TARGET=aws` saves a Terraform plan; `plan TARGET=proxmox`
runs the Proxmox and DNS read-only preflight. Platform-specific mechanics differ,
but neither platform is an implicit fallback. The `vm-*` helpers explicitly address
Proxmox and do not select a generic bootstrap target. `bootstrap:test` needs no
target because it runs offline tests for both.

Automated `destroy-plan`, `destroy` and `destroy-cleanup` support only `TARGET=aws`.
Proxmox disposal is a separately approved manual operation; see its installation
guide.

## Tests

`task bootstrap:test` runs only the offline bootstrap Python and Proxmox shell tests,
not unrelated service or backup tests. Use `task test` for the full Python suite.
Python coverage is in [`tests/test_bootstrap.py`](../tests/test_bootstrap.py) and
[`tests/test_bootstrap_config.py`](../tests/test_bootstrap_config.py).
For mocked Terraform tests and their prerequisites, see the
[AWS Terraform module](../terraform/aws-vm/README.md).
