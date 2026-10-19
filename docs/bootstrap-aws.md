# Bootstrap on AWS

Terraform provisions an on-demand x86_64 Ubuntu EC2 host, encrypted persistent EBS
at `/storage`, an Elastic IP, and SSH/HTTPS restricted to an explicit administrator
CIDR. Ansible configures Traefik/Homepage and optional managed DNS. No automatic
adoption, private subnet, Spot or ARM bootstrap is supported.

**EC2, EBS and public IPv4 charges apply. Failures leave resources/state intact;
stopping EC2 does not eliminate all charges. Teardown is separately approved.**

## Prerequisites and inputs

Use a Linux controller with [Task](https://taskfile.dev/docs/installation),
Python 3.11+ with PyYAML (`python3 -c 'import yaml'`), Terraform >= 1.5, AWS CLI, Ansible, Git, SSH,
`ssh-keygen`, curl, controller Python's `netaddr>=0.10.1`, and the collections from
`ansible/requirements.yml`. Install netaddr in the same environment as Ansible.
Supply AWS credentials through the standard chain in the
approved account/profile, never through YAML or CLI access-key arguments.

The identity needs the template's EC2/network/EBS/EIP/IAM permissions, STS identity
and SSM Run Command/read permissions for the owned instance. The guest receives
only its SSM role. No administrator AWS credentials are transferred. The private
SSH key must match the public key supplied to Terraform; AWS bootstrap requires
the `ubuntu` user. Use a Cloudflare domain and scoped DNS token, ACME email, and
an optional existing AdGuard endpoint. HTTPS is recommended; HTTP is supported on
operator-approved trusted networks with unencrypted credentials and API traffic.
See [Bootstrap DNS](bootstrap-dns.md).

```bash
ansible-galaxy collection install -r ansible/requirements.yml
task bootstrap:init TARGET=aws
```

Initialization fills `aws.expected_account_id` from `aws sts get-caller-identity`
and `aws.admin_source_address` from this controller's public IPv4 plus `/32`.
The public SSH key is referenced by path under `vm`, not copied into source YAML.
It reads no private key and creates
no AWS resources. For a different existing public key:

```bash
task bootstrap:init TARGET=aws BOOTSTRAP_SSH_PUBLIC_KEY=~/.ssh/my-aws-key.pub
```

The selected public-key path and corresponding private-key path are written to new
`bootstrap.yaml` inputs. Existing source key paths are preserved. Initialization
fills only the exact account/CIDR placeholders. Configured values and all
other edits remain untouched. Subsequent runs with no placeholders need neither
AWS credentials nor IP detection. Detection failures stop with placeholders intact;
fix credentials, networking or the key path and rerun initialization.

No target is selected by default. Pass `TARGET=aws` on each target-selecting
bootstrap command; Proxmox uses the same interface with `TARGET=proxmox`. To use an
existing custom directory, also pass its `BOOTSTRAP_CONFIG_DIR` on every command.
Never create a fresh backend to resume resources recorded in a different directory.

Privately edit only `config/bootstrap-aws/bootstrap.yaml`, including `secrets`.
Native Ansible and Terraform inputs are generated under `generated/` when commands run.
Never edit those generated files.
See [inputs and safety](bootstrap-configuration.md). Review the detected account,
administrator CIDR and public-key path, then replace the remaining placeholders. Select a
published repository branch, tag or commit. Use a dedicated deployment subdomain,
not the homelab's existing base/wildcard. Docker bind mounts must be below `/storage/`.

## Plan, apply and initialize storage

```bash
task bootstrap:plan TARGET=aws
task bootstrap:apply TARGET=aws
```

Plan uses the canonical Terraform root with a dedicated backend, native variable
validation, the AWS provider account guard and provider-data preconditions. It
checks configured DNS credentials/conflicts before provisioning. Review the normal
Terraform plan, especially any replacement, deletion or newly selected AMI. Pin
`ami_id` if future plans must retain the same image. Apply prompts for approval and
applies the **saved plan**, never silently generates another one.

For `repository_ref`, a SHA stays fixed and a branch follows its remote tip during
configuration. See [repository revisions and configuration updates](bootstrap-configuration.md#repository-revisions-and-configuration-updates)
for updating code on an already provisioned host.

After EC2 health and SSM registration, Ansible waits for cloud-init, obtains the
SSH host key through authenticated SSM and configures strict OpenSSH trust. No
TOFU or disabled-host-key fallback is used. SSM Agent, instance-role permissions
and outbound AWS reachability are prerequisites; a failure stops with resources
intact.

**Automatic first-format policy:** approving apply/configure also authorizes initial
formatting of the exact Terraform-owned data volume, but only after Ansible verifies
its NVMe serial, snapshot-free origin, owned attachment and deployment tag, absent
partitions/signatures, and absence of a previous format-attempt marker. An empty
`blkid` result alone never authorizes formatting. No manual volume-ID entry is needed.

To resume a provisioned guest after correcting a reported cause, explicitly approve:

```bash
task bootstrap:configure TARGET=aws
```

Existing whole-disk ext4 is mounted without formatting. Other filesystems,
partitioned disks and unrecognized signatures stop configuration for review.
A one-time controller marker is written before the native filesystem module runs;
an interrupted attempt cannot silently authorize another format. Never delete that
marker to retry formatting. Verification never formats storage.
The mount must match the EBS identity before Docker runs;
cloud-init also installs Docker's `/storage` mount prerequisite.

## Acceptance and recovery

Native Ansible modules configure DNS, the existing host roles, the selected Git
checkout and private Compose files. Compose waits for running/healthy services.
Acceptance additionally checks the controller's DNS resolution, trusted HTTPS for
both routes, the live Homepage-to-Traefik widget, persistent ACME/log paths, stable
containers and no recreation on repeat Compose deployment.

```bash
task bootstrap:verify TARGET=aws
```

Verification repeats Compose but never provisions, formats or rewrites DNS. A
repeat `bootstrap:plan` should show no infrastructure changes; run it only within
the approved scope. An unexpected create/replace in Terraform's plan must be
reviewed, not applied.

Correct reported causes before explicitly resuming `configure` or reviewing a new
plan. Do not discard state, replace host trust, force formatting or run standalone
`aws-vm:*` tasks against this backend. Cloud-init changes do not rerun on an existing
guest. A stopped instance is not automatically restarted by configure; inspect and
approve its lifecycle separately using AWS tools.

## Teardown

Back up any data you need. Full destruction deletes both disks. Use the original
configuration and backend:

```bash
task bootstrap:destroy-plan TARGET=aws DELETE_DATA=1
task bootstrap:destroy TARGET=aws
```

The first command temporarily uses Terraform's native lifecycle override solely
to plan approved data-volume destruction; it removes that override even on failure
and displays the saved destroy plan. It never weakens the tracked template. Review
the plan before the second command's confirmation. Task's native `--yes` should
only be used for a previously reviewed unattended run.

Before Terraform applies destruction, Ansible stops running containers, the Docker
socket and daemon, and cleanly unmounts `/storage` on the dedicated guest. It uses
the deployment's strict SSH trust. A stopped, terminated or absent instance is not
restarted; transitional states, SSH failures and failed unmounts stop teardown
before Terraform runs. This also handles guests where Docker was never installed.

Terraform owns deletion order and state locking. After its state listing is empty,
Ansible checks the original AWS account and independently verifies instance
termination, both disks, Elastic IP, VPC, SSH key pair and dedicated IAM resources.
It also checks for owned snapshots linked to either disk. These checks use bounded
read-only AWS CLI calls; the operator needs the corresponding EC2 describe and IAM
get permissions, including `ec2:DescribeSnapshots`. Permission errors are not
treated as proof of deletion. Snapshots are reported, never automatically deleted.

Only after those checks pass are exact deployment-owned DNS records and generated
controller artifacts removed. Public inputs and secrets are retained for reuse.
If post-destroy verification or DNS cleanup fails, recovery files remain. Correct
the cause and retry cleanup without replaying the saved destroy plan:

```bash
task bootstrap:destroy-cleanup TARGET=aws
```

Use the same `BOOTSTRAP_CONFIG_DIR` if you selected a custom directory. Never use
fresh state as a cleanup shortcut. Operator backups, snapshots and manual DNS are
outside Terraform's ownership and may need separately approved cleanup or remain
billable.
