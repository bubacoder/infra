# Bootstrap inputs and safety

Bootstrap delegates infrastructure to Terraform, guest configuration to Ansible,
and container lifecycle to Compose. A small Python configuration compiler prepares
their inputs; Task sequences the native commands. Python does not own infrastructure
state, DNS ownership, SSH trust or storage initialization.

This guide is the shared reference for operators and agents. For the complete
installation and teardown procedures, choose the [AWS guide](bootstrap-aws.md) or
[Proxmox guide](setup.md). Provider settings and DNS ownership are covered in
[Bootstrap DNS](bootstrap-dns.md).

## Controller prerequisites

Use a separate Linux controller with Git, SSH, `ssh-keygen`, curl,
[Task](https://taskfile.dev/docs/installation), Ansible, and Python 3.11+ with PyYAML.
Clone the repository and run bootstrap commands from its root. See the selected
installation guide for AWS/Proxmox-specific tools and access requirements.

If Ansible is missing, `sudo ansible/bootstrap-ansible.sh` installs it on a supported
controller. On Ubuntu, install missing YAML support with
`sudo apt install python3-yaml`; check it with `python3 -c 'import yaml'`.
Install the pinned collections in the controller's Ansible environment:

```bash
ansible-galaxy collection install -r ansible/requirements.yml
```

## One private operator input

Every target-selecting bootstrap command requires `TARGET=aws` or `TARGET=proxmox`.
Neither is a default. Missing, empty or invalid targets fail before commands run.

Initialization creates only `bootstrap.yaml`, without overwriting operator edits:

| Target | Default input/state directory | Tracked template |
| --- | --- | --- |
| AWS | `config/bootstrap-aws/` | [AWS](../config-example/bootstrap-aws.yaml) |
| Proxmox | `config/bootstrap-proxmox/` | [Proxmox](../config-example/bootstrap-proxmox.yaml) |

If `bootstrap.yaml` is missing, initialization requires an empty deployment
directory. Restore the original source when recovering an existing deployment;
never discard its state or recovery records to make initialization proceed.

Define VM name, user and SSH key paths once under `vm`. Set host/application
settings under `host`, provider inputs under `proxmox` or `aws`, DNS settings under
`dns`, Cloudflare/optional AdGuard credentials under `secrets`, and ordered host
roles and applications under the explicit `roles` and `services` lists.
The schema rejects unknown fields, duplicate YAML keys and mismatched targets.
Native Terraform/Ansible validation still applies after conversion.

Keep SSH keys in their original controller location and reference their paths under
`vm`. Provisioning transfers only the public key directly to Proxmox. No private
key is read by the compiler. Initialization creates no VM. AWS initialization
performs the [documented account/IP detection](bootstrap-aws.md#initialize).
Use `BOOTSTRAP_SSH_PUBLIC_KEY=~/.ssh/<key>.pub` when initializing a new source to
select another key pair. Existing source key settings are not overwritten.

The entire `bootstrap.yaml` is secret-bearing, including when most fields look
public. Edit it privately; never share it with an agent. Vault-encrypted input is
not supported. Native Ansible loads/renders generated credentials with `no_log: true`.
Never put credentials in Terraform variables, command arguments or logs. Do not
use `--diff` or debug secret variables.
Keep source/generated files private (`0600`) and deployment/generated directories
`0700`. Unsafe permissions and symlinked configuration paths are rejected.

Use `BOOTSTRAP_CONFIG_DIR=config/<directory>` to select a different deployment input/state
directory. Keep it under the ignored `config/` directory. Use one directory per
deployment; do not reuse initialized inputs/state for a different account/host.
Pass the same explicit `TARGET` and custom directory on every command. A mismatch
between `TARGET` and `bootstrap.yaml` is rejected, including during reinitialization.
For AWS, always use the deployment's existing Terraform backend when managing
provisioned resources; never substitute a fresh empty state directory.
AWS credentials use the normal credential chain (for example an explicitly
selected `AWS_PROFILE`); credentials are never copied to the guest.

Use [safe inspection](#safe-configuration-inspection) after editing. Native inputs
are prepared automatically; [generated files](#state-and-ownership) are not edited.

## Safe configuration inspection

```bash
task bootstrap:show-config TARGET=aws
task bootstrap:show-config TARGET=proxmox
task bootstrap:show-config TARGET=aws BOOTSTRAP_CONFIG_DIR=config/my-test
```

Run only the command for the selected deployment. For agents, this is the only
supported configuration inspection interface. Do not read `bootstrap.yaml`,
generated credentials, Terraform state or other secret-bearing inputs with file
tools, `cat`, `grep` or ad-hoc scripts. Operators enter secrets privately, never
through chat, command arguments, logs or Terraform inputs.

The offline compiler reads the private source internally and prints only
allowlisted non-secret settings. It does not generate files, read Terraform state
or private SSH keys, or contact providers. Parser failures never display private
values. Put credentials only under `secrets`; this is not a general-purpose secret
scrubber. Output is not anonymized: redact identifiers before sharing evidence.
On failure, have the operator correct the file privately; do not fall back to raw
file reads. `bootstrap:plan` is a separate, authorized live preflight.

To check live provisioning progress without running another apply/verify or
changing generated files, receipts or pinned SSH trust, run:

```bash
task bootstrap:status TARGET=proxmox BOOTSTRAP_CONFIG_DIR=config/<deployment>
# or: task bootstrap:status TARGET=aws BOOTSTRAP_CONFIG_DIR=config/<deployment>
```

Status takes one bounded read-only snapshot: provider VM/EC2 state, Proxmox guest
agent and cloud-init (or AWS SSM), and, once guest SSH was already pinned by
bootstrap, guest cloud-init and the selected K3s service/node. It neither waits
for completion nor creates a guest, changes SSH trust, applies roles or regenerates
native inputs. Pending checks are reported without failing; provider access or VM
identity mismatches fail safely. Repeat status as needed while an apply is running.
Status is **not** acceptance: run `bootstrap:verify` after apply completes.

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
New local roles do not need a compiler allowlist entry, but must exist before selection.

For a default single-server Kubernetes guest on either target, select the local
[`k3s` role](../ansible/roles/k3s/README.md):

```yaml
roles:
  - debian_base
  - k3s
services: []
host: {}
dns:
  enabled: false
secrets: {}
```

Keep the template's VM/provider settings and choose a fresh dedicated VM. K3s uses
its bundled Traefik and ServiceLB, so bootstrap-managed Docker applications cannot
be selected alongside it. Existing Docker defaults are unchanged. No domain, TLS
credentials or published repository ref is needed for this profile. The default
K3s datastore and local volumes live on the OS disk, including on AWS; the separate
AWS `/storage` disk is not used by K3s. See the role guide for access and backups.

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
the role list is nonempty. Selecting `k3s` additionally runs its read-only checks
for service, credentials permissions, API, nodes and default packaged deployments.
Other role-specific workloads require their own acceptance checks.

## Repository revisions and configuration updates

Repository settings are used only when services are selected.
`host.repository_ref` accepts a published branch, tag or full commit SHA.
Ansible passes this value directly to its native Git module during configuration:
a full SHA checks out that exact commit; a branch follows its current remote tip.
Git reports unavailable refs when checking out the guest repository, not during
infrastructure planning.

To deploy a published branch update, rerun
`task bootstrap:configure TARGET=aws` or `TARGET=proxmox` with the same directory.
The existing host picks up the branch update without reprovisioning. With a SHA,
update `host.repository_ref` to the new commit first. Local guest edits are preserved
(`force: false`). Infrastructure or cloud-init changes still require their own
reviewed plan; configure does not apply Terraform or rerun cloud-init.

## State and ownership

Every operational command prepares native inputs under the selected directory:

| Generated file | Consumer | Contents |
| --- | --- | --- |
| `generated/host.yaml` | Ansible | Non-secret host, roles, services and DNS settings |
| `generated/secrets.yaml` | Ansible only | Service credentials, never Terraform inputs |
| `generated/aws.tfvars.json` | Terraform, AWS only | Infrastructure inputs and public SSH key |
| `generated/ubuntu-cloud.env` | Proxmox scripts only | VM inputs derived from the same identity |

Never edit generated files: subsequent commands replace them. State, plans and
recovery records stay in the original deployment directory, not `generated/`;
input regeneration never deletes them.

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

These are `task bootstrap:<command>` commands. Pass the explicit target and the
same custom directory, if any, throughout a deployment:

| Command | Effect |
| --- | --- |
| `init` | Create the single private input; AWS also detects initial account/IP defaults |
| `show-config` | Inspect allowlisted settings offline; no generation or provider access |
| `status` | Bounded read-only snapshot of VM, agent/cloud-init and trusted guest/K3s readiness; no generation or writes |
| `plan` | AWS: save a Terraform plan and run preflight. Proxmox: read-only VM/DNS preflight |
| `apply` | AWS: apply the reviewed saved plan. Proxmox: create/start a fresh VM. Then configure and verify |
| `configure` | Apply selected roles/services to an existing guest and verify; never provision |
| `verify` | Check guest/storage and selected services; no role application, formatting or DNS writes. Repeat Compose only for selected services |
| `destroy-plan`, `destroy`, `destroy-cleanup` | AWS-only reviewed destruction and recoverable cleanup; see [AWS teardown](bootstrap-aws.md#teardown) |

Proxmox `vm-preflight`, `vm-provision` and `vm-wait` explicitly address Proxmox;
they are not a generic target fallback. Proxmox disposal is separately approved
and manual. `bootstrap:test` needs no target because it runs offline tests for both.

## Tests

`task bootstrap:test` runs only the offline bootstrap Python and Proxmox shell tests,
not unrelated service or backup tests. Use `task test` for the full Python suite.
Python coverage is in [`tests/test_bootstrap.py`](../tests/test_bootstrap.py),
[`tests/test_bootstrap_config.py`](../tests/test_bootstrap_config.py), and
[`tests/test_bootstrap_status.py`](../tests/test_bootstrap_status.py).
For mocked Terraform tests and their prerequisites, see the
[AWS Terraform module](../terraform/aws-vm/README.md).
