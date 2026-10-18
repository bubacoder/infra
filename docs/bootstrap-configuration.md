# Bootstrap inputs and safety

Bootstrap delegates infrastructure to Terraform, guest configuration to Ansible,
and container lifecycle to Compose. Task only sequences their native commands.

This guide is the shared reference for operators and agents. For the complete
installation and teardown procedures, choose the [AWS guide](bootstrap-aws.md) or
[Proxmox guide](setup.md). Provider settings and DNS ownership are covered in
[Bootstrap DNS](bootstrap-dns.md).

## Separate inputs

Every target-selecting bootstrap command requires `TARGET=aws` or `TARGET=proxmox`.
Neither is a default. Missing, empty or invalid targets fail before commands run.

Choose either installation:

```bash
task bootstrap:init TARGET=aws
task bootstrap:init TARGET=proxmox
```

Defaults are isolated: AWS uses `config/bootstrap-aws/`, Proxmox uses
`config/bootstrap-proxmox/`. Initialization creates the following under the selected
directory, without overwriting configured values:

| File | Consumer | Contents |
| --- | --- | --- |
| `host.yaml` | Ansible | Public host, DNS, application and requested repository settings |
| `aws.tfvars` | Terraform, AWS only | Public infrastructure inputs; native template validation applies |
| `secrets.yaml` | Ansible only | Cloudflare token and optional AdGuard credentials |

Proxmox initialization also creates `ubuntu-cloud.env` in the selected directory
without overwriting an existing file. Keep SSH keys in their original controller
location and reference their paths in `host.yaml`; provisioning transfers only the
public key directly to Proxmox. `BOOTSTRAP_CONFIG_DIR` selects deployment inputs, including those used
by the Proxmox `vm-*` helpers. Initialization does not connect to Proxmox or create a VM.

AWS initialization fills the account ID, administrator public IPv4 `/32`, and SSH
public key in `aws.tfvars` using the active AWS identity, `https://api4.ipify.org`,
and the selected `.pub` file. Only exact template placeholders are replaced;
configured values are never refreshed. Review all detected values before planning.
Use `BOOTSTRAP_SSH_PUBLIC_KEY=~/.ssh/<key>.pub` during initialization to select a
different key (otherwise the existing `host.yaml` path or `~/.ssh/id_ed25519.pub`
is used). New host settings use that path and infer the private-key path by removing
`.pub`; no private key is read. Proxmox initialization does not call AWS or detect
a public IP. Both targets use the selected key paths in new host settings.

The directory is mode `0700`, files `0600`. Edit them privately. Secrets may be
encrypted with `ansible-vault encrypt <selected-directory>/secrets.yaml`; provide a
Vault identity through Ansible's normal controller configuration. Never put
credentials in Terraform variables, command arguments, host settings or logs.
Ansible loads and renders secret-bearing tasks with `no_log: true` and mode `0600`.
Do not use `--diff` or debug secret variables.

Use `BOOTSTRAP_CONFIG_DIR=config/<directory>` to select a different deployment input/state
directory. Keep it under the ignored `config/` directory. Use one directory per
deployment; do not reuse an initialized backend for a different account/host.
Pass the same explicit `TARGET` and custom directory on every command. A mismatch
between `TARGET` and `host.yaml` is rejected, including during reinitialization.
Always use the deployment's existing backend when managing provisioned resources;
never substitute a fresh empty state directory.
AWS credentials use the normal credential chain (for example an explicitly
selected `AWS_PROFILE`); credentials are never copied to the guest.

`host.yaml` accepts a published branch, tag or full commit SHA as `repository_ref`.
Terraform validates infrastructure inputs; Ansible's native argument specification
validates host/service inputs.

## Repository revisions and configuration updates

For example, `repository_ref: main` or `repository_ref: feature/bootstrap` is valid.
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
interface. Do not read `secrets.yaml`, Terraform state or other secret-bearing
inputs with file tools, `cat`, `grep` or ad-hoc scripts. Operators enter secrets
privately; never copy them into chat, command arguments, logs or Terraform inputs.

The offline playbook opens only the **non-secret** `host.yaml` and prints
allowlisted settings. It never opens `secrets.yaml`, Terraform state, provider
credentials or other private inputs. Unknown fields are omitted. Keep secrets
out of the public file; this is not a general-purpose secret scrubber. Output is
not anonymized: redact identifiers before sharing outside the trusted session.
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
Python bootstrap coverage is in [`tests/test_bootstrap.py`](../tests/test_bootstrap.py).
For mocked Terraform tests and their prerequisites, see the
[AWS Terraform module](../terraform/aws-vm/README.md).
