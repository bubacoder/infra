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
Install `netaddr>=0.10.1` in the same Python environment as Ansible; the
`ansible.utils.ipaddr` filter uses it to validate opt-in Traefik CIDRs. This also
applies when Ansible was already installed outside the bootstrap setup script.

If Ansible is missing, `sudo ansible/bootstrap-ansible.sh` installs it on a supported
controller. On Ubuntu, install missing YAML support with
`sudo apt install python3-yaml`; check it with `python3 -c 'import yaml'`.
Install the pinned collections in the controller's Ansible environment:

```bash
ansible-galaxy collection install -r ansible/requirements.yml
```

## One metadata-only operator input

Every target-selecting bootstrap command requires `TARGET=aws` or `TARGET=proxmox`.
Neither is a default. Missing, empty or invalid targets fail before commands run.

Initialization creates only `bootstrap.yaml`, without overwriting operator edits:

| Target | Default input/state directory | Tracked template |
| --- | --- | --- |
| AWS | `config/bootstrap-aws/` | [AWS](../config-example/bootstrap-aws.yaml) |
| Proxmox | `config/bootstrap-proxmox/` | [Proxmox](../config-example/bootstrap-proxmox.yaml) |

Initialization accepts `PROFILE=docker` (the default for a new source) or
`PROFILE=k3s` on either target. K3s selects `debian_base`, `k3s`, no Docker services,
disabled DNS management and no service credentials, with a dedicated `k3s-<target>`
VM name. VM/provider sizing, storage, networking and SSH settings still come from
the target template and must be reviewed before planning:

```bash
task bootstrap:init TARGET=proxmox PROFILE=k3s BOOTSTRAP_CONFIG_DIR=config/my-k3s
# Optional direct controller access, using DNS maintained outside bootstrap:
task bootstrap:init TARGET=proxmox PROFILE=k3s BOOTSTRAP_CONFIG_DIR=config/another-k3s \
  K3S_API_HOST=k3s.example.com K3S_CONTEXT=my-k3s
```

`K3S_API_HOST` opts into installing a controller context; `K3S_CONTEXT` defaults
to `k3s-<target>` and is valid only with that host. These are non-secret settings.
The profile does not create DNS records or reserve DHCP addresses. To enable
bootstrap-managed AdGuard DNS, privately set `host.domain` to the API's fully
qualified name, enable `dns`, list every endpoint and supply its credentials.
Existing sources are never rewritten to switch profiles or access settings;
conflicting explicit initialization options fail instead of silently migrating them.

If `bootstrap.yaml` is missing, initialization requires an empty deployment
directory. Restore the original source when recovering an existing deployment;
never discard its state or recovery records to make initialization proceed.

Define VM name, user and SSH key paths once under `vm`. Set host/application
settings under `host`, provider inputs under `proxmox` or `aws`, DNS settings under
`dns` (including Cloudflare/AdGuard credential **file references**), and ordered host
roles and applications under the explicit `roles` and `services` lists.
The schema rejects unknown fields, duplicate YAML keys and mismatched targets.
Native Terraform/Ansible validation still applies after conversion.

Keep SSH keys in their original controller location and reference their paths under
`vm`. Provisioning transfers only the public key directly to Proxmox. No private
key is read by the compiler. Initialization creates no VM. AWS initialization
performs the [documented account/IP detection](bootstrap-aws.md#initialize).
Use `BOOTSTRAP_SSH_PUBLIC_KEY=~/.ssh/<key>.pub` when initializing a new source to
select another key pair. Existing source key settings are not overwritten.

The current schema keeps credential values out of `bootstrap.yaml`: credentials
must be file references beside their related DNS settings, never literal strings.
There is no top-level `secrets` section:

```yaml
dns:
  enabled: true
  cloudflare_zone: example.com # AWS-managed public DNS only.
  cloudflare_token: {file: ./secrets/cloudflare-token}
  adguard_urls: [https://adguard.example.com]
  adguard_username: {file: ~/.secrets/adguard-username}
  adguard_password: {file: ./secrets/adguard-password}
```

Relative paths resolve against the directory containing `bootstrap.yaml`, not
the working directory; absolute paths and `~` are supported. File contents must
be nonempty UTF-8 text, at most 1 MiB. Only trailing CR/LF characters are removed;
spaces, tabs and interior newlines are preserved. References require exactly one
`file` key. Files must belong to the current controller user, be regular files
with mode `0400` or `0600`, and have no symlinked path components. Missing files,
unsafe permissions, invalid UTF-8 and NUL bytes fail without exposing their paths
or contents. File references are validated even for disabled features.

Credential reads open each directory component with no-follow semantics and use
directory descriptors for subsequent lookups. Replacing a parent path with a
symlink cannot redirect an in-progress read.

Inspection/status validate reference syntax without opening secret files.
Operational preparation resolves the files into private `state/generated/secrets.yaml`
for Ansible; public artifacts contain neither credential values nor references.
Secret-file changes are included in saved-plan fingerprints, so rotating a file
invalidates an already reviewed plan. Native Ansible loads/renders generated
credentials with `no_log: true`.

The compiler resolves external inputs before pure artifact rendering. The same
fingerprint function binds rendered inputs to saved plans and rechecks freshly
resolved inputs after planning, including credential rotations during that run.

After successful current-schema validation, the source can be inspected by agents
without revealing credential values. Hostnames, IPs, email and file paths are
still potentially sensitive metadata. This is not a general-purpose scrubber:
never paste credentials into comments or unrelated fields. Legacy sources with
inline secrets remain secret-bearing until privately migrated.

Never read referenced secret files or generated credentials through an agent;
never put their values in Terraform variables, command arguments or logs. Do not
use Ansible `--diff` or debug secret variables. Keep source/generated files `0600`
and deployment/generated directories `0700` for metadata and artifact privacy.

### Migrating an existing source

An operator must privately move each old inline credential to an owner-private
file, add its `{file: path}` reference under `dns`, then remove the old `secrets`
section. Do not paste the old source or secret values into chat. Retain existing
VM/provider identity, DNS ownership, state and recovery data; no live resources
change merely because credentials are externalized. Run `bootstrap:show-config`,
then prepare/review a new plan before applying. The compiler deliberately rejects
legacy sections and literal credentials rather than silently accepting them.

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

Run only the command for the selected deployment. Use this command first to
validate the current file-only schema without opening secret files. A successfully
validated `bootstrap.yaml` contains metadata/file references and can then be read
by agents. If validation fails, do not fall back to raw reads of a potentially
legacy secret-bearing source; have the operator correct or migrate it privately.
Never read referenced files, generated credentials, Terraform state or other
secret-bearing inputs with file tools, `cat`, `grep` or ad-hoc scripts. Operators
enter secrets privately, never through chat, command arguments or Terraform inputs.

The offline compiler reads the private source internally and prints only
allowlisted non-secret settings. It does not generate files, read Terraform state
or private SSH keys, or contact providers. Parser failures never display private
values. It omits credential file references as well as secret contents. Output
is not anonymized: redact identifiers before sharing evidence.
Offline inspection enforces the same deployment-name rule as native Ansible:
DNS management or Docker services require a fully qualified lowercase
`host.domain`. Short API names remain valid only for externally managed K3s access
with bootstrap DNS disabled. No provider calls or generation are needed to find
this configuration error.
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
bootstrap, guest cloud-init and the selected K3s service/node. With opted-in K3s
access, it also checks the deployment-owned local context and Ready node. It neither waits
for completion nor creates a guest, changes SSH trust, applies roles or regenerates
native inputs. Pending checks are reported without failing; provider access or VM
identity mismatches fail safely. Repeat status as needed while an apply is running.
Status is **not** acceptance: run `bootstrap:verify` after apply completes.
With a responding Proxmox agent, status reports cloud-init's allowlisted state
and phase separately from guest networking and K3s readiness. Agent absence does
not establish a boot failure: first-boot package installation may still be running.
Recovery hints retain the selected deployment directory, never recreate an
existing VM, and never start, configure or repair it automatically. Cloud-init
errors are diagnosed privately; raw logs and error details are not printed.

## Selecting host roles and applications

Both target templates explicitly select the existing Docker host setup:

```yaml
roles:
  - debian_base
  - debian_docker_host
services:
  - core/traefik
  - core/homepage
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
```

Keep the template's VM/provider settings and choose a fresh dedicated VM. K3s uses
its bundled Traefik and ServiceLB, so bootstrap-managed Docker applications cannot
be selected alongside it. Existing Docker defaults are unchanged. No domain, TLS
credentials or published repository ref is needed for this profile. The default
K3s datastore and local volumes live on the OS disk, including on AWS; the separate
AWS `/storage` disk is not used by K3s. See the role guide for access and backups.

Direct controller-side `kubectl` and K9s access is explicitly opt-in using
`k3s.access` in the private source. It configures K3s's API TLS hostname and,
after authenticated guest verification, securely installs a unique local context.
See [K3s access](../ansible/roles/k3s/README.md#access-and-lifecycle) for the
required DNS, network and controller setup. Existing inputs without this section
continue using the guest-only K3s profile.

Cilium is independently opt-in for a fresh K3s VM: select roles
`[debian_base, k3s_cilium, k3s]`. Role selection is the only switch; there is no
`k3s.cilium` settings block.
The Cilium role must precede K3s to prepare networking before its first start;
the compiler and native validation reject invalid ordering.
Omit the role to preserve default Flannel networking on a fresh host.
See [Cilium networking](../ansible/roles/k3s_cilium/README.md)
for installation, acceptance checks and lifecycle guards. Bootstrap does not
automatically migrate existing CNIs, uninstall Cilium or upgrade its pinned chart.

Managed ingress is separately opt-in: select `k3s_traefik` after `k3s` and supply
`k3s.traefik` settings as described in the
[Traefik role](../ansible/roles/k3s_traefik/README.md). The adapter configures the
bundled controller with shared dynamic file-provider policies, a Secret-backed
Cloudflare resolver and explicitly selected persistent ACME storage. It needs
`host.acme_email` and a `dns.cloudflare_token` file reference, even with `services: []` and DNS
management disabled. Its application domain is independent of the API hostname.
Only explicitly selected supported middleware chains are loaded; auth/plugin
dependencies fail closed. Existing manually managed Traefik objects are never
automatically adopted. Omitting this role/feature preserves the default K3s
profile and does not require TLS credentials.

For a host without Docker or bootstrap-managed applications, retain the VM/provider
sections and replace these configuration sections:

```yaml
roles:
  - debian_base
services: []
host: {}
dns:
  enabled: false
```

An empty role list is also allowed for a provisioned guest with no role-based
configuration. `debian_base` is not silently inserted. Removing a role or service
from the lists does **not** uninstall software, stop existing containers, or delete
data/DNS. Such lifecycle changes require separately reviewed operations.

Currently supported services are `core/traefik` and `core/homepage`.
The legacy names `security/traefik` and `dashboard/homepage` are accepted and
normalized in memory; existing operator inputs need not be rewritten. Selecting
both names for the same service is rejected as a duplicate.
Any nonempty service list requires `debian_docker_host`; Homepage also requires
Traefik for its bootstrap routing/widget profile. Traefik alone is supported.
The guest's generated service-management profile contains only selected services.

Settings are required only by enabled features:

| Feature | Required settings |
| --- | --- |
| Any bootstrap service | All `host` fields from the template and `dns.cloudflare_token: {file: path}` for TLS |
| Docker role, even with no services | `host.docker_volumes`; AWS bind mounts must remain below `/storage/` |
| Enabled DNS management | `host.domain`; AWS also needs `dns.cloudflare_zone` and a `dns.cloudflare_token` file reference |
| Enabled DNS with existing AdGuard endpoints | `dns.adguard_username` and `dns.adguard_password` file references |
| No services and DNS disabled | No domain, ACME email, repository settings, or service credentials required |

The last row excludes explicitly enabled `k3s.traefik`: that feature requires its
own domain/storage/middleware settings, ACME email and private Cloudflare token.

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

```text
<deployment>/
├── bootstrap.yaml             # The user-edited metadata/file-reference input
└── state/                    # Bootstrap-managed private artifacts
    ├── generated/
    ├── backups/
    ├── plans/
    ├── known_hosts
    ├── dns-state.yaml
    └── k3s-access-receipt.json
```

Keep referenced credential files outside this folder, or explicitly choose their
paths; bootstrap never moves or edits them. All managed artifacts belong under
`state/`, with directories mode 0700 and files mode 0600. The user-facing
`BOOTSTRAP_CONFIG_DIR` still names the deployment root, not `state/`.

| Generated file | Consumer | Contents |
| --- | --- | --- |
| `state/generated/host.yaml` | Ansible | Non-secret host, roles, services and DNS settings |
| `state/generated/secrets.yaml` | Ansible only | Service credentials, never Terraform inputs |
| `state/generated/aws.tfvars.json` | Terraform, AWS only | Infrastructure inputs and public SSH key |
| `state/generated/ubuntu-cloud.env` | Proxmox scripts only | VM inputs derived from the same identity |
| `state/generated/k3s-traefik-*.yaml` | Optional Traefik role | Public ConfigMap/PVC/HelmChartConfig projections; no credential values |

Never edit generated files: subsequent commands replace them. State, plans and
recovery records stay under `state/`, outside `state/generated/`;
input regeneration never deletes them.

AWS runs the canonical `terraform/aws-vm` root directly with an isolated local
backend at `<selected-directory>/state/aws.tfstate` and provider cache in
`state/.terraform/`. Saved plans live in `state/plans/`; local Kubernetes access
backups live in `state/backups/`. Terraform owns resource identity, dependencies,
locking, refresh and destruction. Do not use standalone `aws-vm:*` tasks against
this backend. Review native plans: missing resources can be recreated by Terraform
and changed provisioning inputs can propose replacement. Never apply an unreviewed
replacement plan.

Successful AWS planning also saves a private input/plan fingerprint in `state/`.
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

Legacy top-level artifacts are rejected rather than read as fallback inputs. A
one-time, separately approved layout migration must preserve the original bytes,
permissions and ownership: move generated inputs to `state/generated/`, plans to
`state/plans/`, access backups to `state/backups/`, and remaining receipts/trust
files to `state/`. Keep `bootstrap.yaml` and the deployment root identity unchanged;
never regenerate trust or discard recovery records to clear a layout guard.
Existing AWS backends additionally require Terraform's reviewed backend migration
and new saved plans; never silently initialize an empty replacement state.

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
| `destroy-plan`, `destroy`, `destroy-cleanup` | Reviewed target-specific destruction and recoverable cleanup; see [AWS teardown](bootstrap-aws.md#teardown) or [Proxmox cleanup](setup.md#cleanup) |

Proxmox `vm-preflight`, `vm-provision` and `vm-wait` explicitly address Proxmox;
they are not a generic target fallback. Destruction uses a common command contract
with separate AWS Terraform and Proxmox native implementations, each requiring
review of the original deployment's identities before deletion. `bootstrap:test`
needs no target because it runs offline tests for both.

## Tests

`task bootstrap:test` runs only the offline bootstrap Python and Proxmox shell tests,
not unrelated service or backup tests. Use `task test` for the full Python suite.
Python coverage is in [`tests/bootstrap/test_native.py`](../tests/bootstrap/test_native.py),
[`tests/bootstrap/test_config.py`](../tests/bootstrap/test_config.py), and
[`tests/bootstrap/test_status.py`](../tests/bootstrap/test_status.py).
Controller access coverage is in [`tests/bootstrap/test_access.py`](../tests/bootstrap/test_access.py).
Guarded Proxmox destroy coverage is in
[`tests/bootstrap/test_proxmox_destroy.py`](../tests/bootstrap/test_proxmox_destroy.py).
Managed ingress coverage is in
[`test_traefik.py`](../tests/bootstrap/test_traefik.py) and
[`test_traefik_native.py`](../tests/bootstrap/test_traefik_native.py), including
actual offline Ansible ownership/precondition and Go-template tests.
For mocked Terraform tests and their prerequisites, see the
[AWS Terraform module](../terraform/aws-vm/README.md).
