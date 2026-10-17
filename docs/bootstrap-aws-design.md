# AWS Bootstrap Target — Design

Status: initial implementation with unit, mocked Terraform and disposable live
stage validation. See [validation boundaries](bootstrap-aws-validation.md) and
[Bootstrap on AWS](bootstrap-aws.md) for usage.
Proxmox remains the default target.

This document records the initial external-DNS design. Current bootstrap now
manages target-aware DNS by default; [Bootstrap DNS](bootstrap-dns.md) supersedes
the DNS checkpoints and external-DNS scope described below. Historical live
validation does not establish live coverage of the new managed-DNS behavior.

## Goal and scope

Keep `task bootstrap:init`, `bootstrap:plan`, and `bootstrap:apply` as the public
workflow. Add AWS EC2 as a target by reusing `terraform/aws-vm`, then converge on
the existing separate-admin-host Ansible and Docker deployment pipeline.

Initial AWS scope: one on-demand Ubuntu x86_64 instance, public IPv4, an Elastic
IP, persistent EBS storage, externally managed DNS, Cloudflare DNS-01 TLS, and
the existing Traefik/Homepage service pair. SSH and HTTPS remain restricted to
the configured administrator CIDR. No public dashboard exposure, private-subnet
deployment, automatic DNS changes, Spot recovery, or automatic destruction.

AWS costs begin during provisioning, including Elastic IP and EBS charges.
Stopping the instance does not eliminate all charges.

## Existing implementation constraints

- `core.py` embeds Proxmox ID/MAC fields in the shared plan and assumes an
  address in `network.expected_ipv4` is the SSH endpoint.
- `__main__.py` dispatches directly to `proxmox`; `deploy.py` imports its
  provisioning, discovery, DNS, and SSH-trust functions.
- `render_config()` also renders the Proxmox environment file.
- AWS cloud-init currently requires a populated Git credentials secret,
  clones an unpinned repository, mounts `/storage`, and installs Ansible.
  This overlaps the separate administrative host bootstrap workflow.
- AWS currently generates the SSH private key inside Terraform state and
  assigns a non-stable public IP. Its AMI lookup selects the newest image.
- The AWS Taskfile `apply` depends on a fresh `plan` and applies automatically;
  it is not suitable for applying bootstrap's exact reviewed plan.
- The EBS comment/README claims `prevent_destroy`, but the resource lacks it.
  The existing attachment also enables `force_detach`.

## Architecture options

| Option | Benefit | Limitation | Decision |
| --- | --- | --- | --- |
| Call `task aws-vm:apply` directly | Smallest integration | Replans, automatic apply, overlapping cloud-init, shared state/key paths | Reject |
| Target adapters plus the existing Terraform template | One shared deployment pipeline; target-specific safety and trust | Requires a small adapter contract and template options | Recommended |
| Separate AWS bootstrap implementation | Minimal disturbance to Proxmox | Duplicates secrets, inventory, repository, and acceptance logic | Reject |

## Configuration contract

Retain version 1 unchanged: absent target means Proxmox. Introduce version 2
with an explicit `target: proxmox | aws`, shared host identity, and exactly one
target-specific configuration block. Do not make AWS accept Proxmox CPU,
bridge, MAC, VM ID, or DHCP-reservation fields.

Illustrative AWS configuration (proposed schema):

```yaml
version: 2
target: aws

# repository is optional, as in version 1.
deployment:
  admin_model: separate
  services:
    - security/traefik
    - dashboard/homepage

vm:
  name: docker-aws
  username: ubuntu
  ssh_public_key: ~/.ssh/id_ed25519.pub

aws:
  account_id: "123456789012"  # Required wrong-account protection.
  region: eu-central-1
  profile: homelab           # Optional standard AWS profile, not credentials.
  ubuntu_version: ubuntu-resolute-26.04
  architecture: x86_64
  instance_type: t3.small
  admin_source_cidr: 203.0.113.10/32
  os_disk_size_gb: 20
  data_disk_size_gb: 30

network:
  expected_ipv4: auto        # Normal for AWS, not a test-only workaround.
  domain: lab.example.com
  dns:
    mode: external
    verify: true

host:
  docker_volumes: /storage/docker-volumes
  timezone: Etc/UTC

tls:
  provider: cloudflare
  acme_email: admin@example.com
  token: replace-with-real-token
```

For the first release require `username: ubuntu`, `architecture: x86_64`, and
Docker volumes beneath `/storage`. Reject unrestricted administrator CIDRs.
Use the supplied SSH public key; never collect AWS access keys in this YAML.
Require a usable matching private key or agent identity and verify authentication
before starting Ansible. Preserve the existing mode-0600 configuration rule.

## Target adapter contract

Keep shared orchestration in `deploy.py`; introduce target dispatch and `aws.py`.
The adapter owns:

1. `resolve_plan`: resolve target identity and immutable provisioning inputs.
2. `preflight`: validate credentials, prerequisites, ownership, and connectivity.
3. `render_provisioning`: write target-specific ignored provisioning inputs.
4. `provision`: create or resume only owned resources using the reviewed plan.
5. `wait_ready`: wait for target health and successful cloud-init completion.
6. `resolve_host`: return the endpoint, resource ID, username, and key reference.
7. `trusted_host_keys`: retrieve SSH host public keys through the trusted control
   plane, not through an unauthenticated network scan.

Represent shared results as `ProvisionedHost`; keep Proxmox ID/MAC and AWS
account/region/instance/EIP in target-specific plan types. SSH, rsync, and
inventory consume the resolved host rather than mutating the input config.
Extract DNS verification into a shared module with target-specific checkpoint
messages. Separate `render_host_config()` from Proxmox VM rendering.

The existing Proxmox adapter retains guest-agent-based address discovery and
host-key verification. Its version 1 behavior must remain unchanged.

## Reuse and extend `terraform/aws-vm`

Add backward-compatible template inputs:

- `bootstrap_mode = "standalone" | "external"`, default `standalone`.
- Optional `ssh_public_key`: use it when supplied, otherwise preserve the
  standalone Terraform-generated key behavior. Do not create a private key
  resource or private-key output value in external mode.
- Optional pinned `ami_id`; bootstrap resolves an official Canonical AMI during
  planning, records it, and supplies it for subsequent plans and resumes.
- Optional Elastic IP allocation/association, enabled by bootstrap.
- External mode cloud-init: set hostname, authorize the supplied key, ensure
  the Ubuntu admin account has noninteractive sudo, install/start SSM Agent,
  and mount persistent storage. Do not clone Git or run Ansible.
- External mode does not create/use the Git credentials secret or its read
  policy. Give the instance the SSM permissions needed for managed-node access.
  Keep existing standalone behavior and outputs compatible.
- Add structured outputs for instance ID, stable public IP, data volume ID,
  resolved AMI, and SSH public key. Read only required outputs, not a dump of
  all sensitive outputs.
- Add the missing data-volume `prevent_destroy` lifecycle guard. Disable forced
  detach in bootstrap mode; replacements/detaches require separate maintenance.

Identify the exact EBS volume and refuse unknown partition tables/filesystems or
mismatched devices. External-mode cloud-init defers formatting to the controller:
an approved Terraform volume-create action grants a one-time initialization
receipt, checked against snapshot-free origin, ownership and exact attachment.
Persist the attempt before mkfs so retries never blindly reformat a disk. Existing
ext4 volumes are mounted without formatting. Raw encrypted EBS bytes need not be
all zeroes, and `blkid` returning no UUID alone does not authorize formatting.
Verify the mounted identity before Ansible or Docker writes under `/storage`.

## Terraform state and plan ownership

Run Terraform directly rather than invoking the current auto-applying Taskfile.
Materialize a runtime working directory from the tracked `.tf` files and
cloud-init templates under `config/terraform/bootstrap/<name>/runtime/`.
This is a regenerated copy of the canonical template, not a separately maintained
AWS definition. Copy an allowlist only; never copy existing state, variables,
plans, backend initialization, or `.terraform` from the standalone directory.

Use a private local backend in that runtime directory initially. Keep state,
backups, lock metadata, saved plan, input JSON, and a deployment manifest under
the ignored deployment directory with directory mode 0700 and file mode 0600.
Back up state securely; losing it is not a reason to create replacement resources.
Pin provider selections with a preserved deployment lockfile.

The manifest binds account, region, host name, template/config/repository hashes,
resolved AMI, resource IDs, and state identity. Changing the target identity or
finding matching-name resources outside this state must stop, not adopt them.
Existing standalone AWS deployments require an explicit, separately reviewed
state migration; never automatically share or import their state.

`bootstrap:plan` may initialize providers, refresh/read AWS state, and write local
plan artifacts, but must not create or alter cloud resources. Inspect
`terraform show -json` privately. Reject every change whose action list includes
`delete` (including replacements), and reject data-volume detach/reassignment.
Print an allowlisted summary, never the raw JSON or state.

During apply, produce and validate a fresh plan, display the AWS account, region,
cost-bearing resource types and changes, obtain confirmation, and apply that
exact saved plan. `YES=1` skips confirmation only, not safety checks. Hold a
deployment orchestration lock and Terraform state locking; do not use
`-target`, `-replace`, `-lock=false`, or automatic destroy/recreate recovery.

## AWS apply flow and checkpoints

1. Validate shared configuration, pinned repository revision, local tools,
   authenticated AWS account/region, and administrator CIDR. Confirm the admin
   host's observed public IP is permitted. Check available instance type/AMI
   and service quotas where observable; IAM success cannot be fully guaranteed
   without actual resource creation.
2. Resolve/reuse the AMI and deployment identity; render external-mode Terraform
   inputs without the Cloudflare token. Generate, inspect, confirm, and apply
   the saved safe plan. Existing owned partial state is resumable.
3. Wait for EC2 running/status checks and SSM registration with bounded timeouts.
   Use SSM Run Command against the exact output instance ID to inspect cloud-init
   status, retrieve only `/etc/ssh/ssh_host_*_key.pub`, and verify the EBS mount.
   Require successful command completion; no unverified SSH/TOFU fallback.
4. Compare network SSH keys with the SSM-obtained public keys and configure
   strict known-host checking. On mismatch, fail rather than deleting an entry.
   SSM Agent installation, instance IAM permissions, outbound HTTPS endpoint
   reachability, and operator Run Command permissions are explicit prerequisites.
5. Discover the Elastic IP and print the DNS checkpoint: base domain and wildcard
   DNS must resolve directly to it. Cloudflare records must be DNS-only, not
   proxied, for the initial restricted-access profile. Stop until observable
   DNS checks pass; rerun resumes the same resources and address. If an expected
   address was explicitly supplied, require an exact match.
6. Render shared Ansible inventory and Docker configuration using the resolved
   endpoint and supplied SSH identity. Run the existing strictly limited Ansible
   play, pinned repository checkout, private secret transfer, and Docker apply.
7. Run existing container/HTTPS/persistence/repeat-deployment acceptance checks,
   plus verify Docker data is actually on the expected EBS volume. Confirm a
   repeat Terraform plan has no unintended infrastructure changes.

DNS-only access works only for clients permitted by the security group; bootstrap
does not promise that Homepage is reachable from arbitrary networks. DNS-01
certificate issuance needs no inbound port 80.

## Failure and security rules

- No Cloudflare token in Terraform variables, state, EC2 user data, SSM commands,
  AWS Secrets Manager, logs, or process arguments. Reuse the current SSH/rsync
  secret transfer after establishing trust.
- AWS credentials use the standard credential chain/profile and are never copied
  onto the guest. Extend `Runner` to support a controlled subprocess environment.
- No automatic EC2 replacement, EBS deletion/detach, resource adoption, or cleanup.
  If cloud-init inputs changed on an existing instance, report that user data is
  not rerun automatically and require explicit maintenance outside bootstrap.
- A checkpoint or failed Ansible/Docker stage leaves chargeable resources running.
  Report their IDs and the resume command; make teardown a separate user-approved
  workflow. The EBS guard means a blanket Terraform destroy may be refused.
- Do not use the existing `save-ssh-key` task, which removes known-host entries
  and writes a global private-key path.

## Implementation sequence and acceptance tests

1. Extract target-neutral host/DNS/rendering helpers and adapter dispatch. Run all
   current bootstrap tests unchanged for version 1 and Proxmox.
2. Add external-mode Terraform inputs, EIP/SSM support, EBS guard, safe mounting,
   and structured outputs. Validate both standalone and external configurations.
3. Add version 2 schema and AWS example; test rejecting mixed-target fields,
   wrong account, unrestricted CIDRs, unsupported architecture/user, and unsafe
   volume paths.
4. Implement private isolated state, pinned inputs, JSON plan inspection, exact
   saved-plan apply, and target ownership. Test destructive plans, changed AMI,
   missing state, partial apply, stale plans, concurrent runs, and secret redaction.
5. Implement SSM readiness/trust and DNS checkpoint. Test failed cloud-init, SSM
   delays/timeouts, wrong instance ID, SSH key mismatch, failed mount, wrong DNS,
   and resume without reprovisioning.
6. In an explicitly approved disposable AWS account, verify fresh bootstrap,
   checkpoint resume, a second complete apply with unchanged instance/EIP/EBS
   and container IDs, trusted HTTPS from the admin host, and blocked access from
   outside the admin CIDR. Review teardown separately and retain data by default.
7. Update setup/configuration docs, README, and AWS standalone docs only after
   support is implemented; do not advertise this proposal as a working target.

## Documentation references

- Terraform saved plans and JSON inspection:
  <https://developer.hashicorp.com/terraform/tutorials/cli/plan>
- Terraform local backend and state locking:
  <https://developer.hashicorp.com/terraform/language/backend/local>
- AWS SSM Run Command:
  <https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command.html>
