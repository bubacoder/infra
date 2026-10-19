# Bootstrap on AWS

Terraform provisions an on-demand x86_64 Ubuntu EC2 host, encrypted persistent EBS
at `/storage`, an Elastic IP, and SSH/HTTPS restricted to an explicit administrator
CIDR. Ansible applies the configured host roles and optional managed DNS. The
templates select Docker with Traefik/Homepage; [role and service selection](bootstrap-configuration.md#selecting-host-roles-and-applications)
also supports Docker-free hosts. Automatic adoption, private subnets, Spot and
ARM bootstrap are not supported.

**EC2, EBS and public IPv4 charges apply. Failures leave resources/state intact;
stopping EC2 does not eliminate all charges. Teardown is separately approved.**

## Prerequisites

Prepare the [shared Linux controller and Ansible collections](bootstrap-configuration.md#controller-prerequisites),
then verify these AWS-specific requirements:

- Terraform >= 1.5 and AWS CLI.
- `netaddr>=0.10.1` in the same Python environment as Ansible.
- An approved AWS account/profile using the standard credential chain. Never put
  AWS access keys in YAML or CLI arguments.
- A matching controller SSH key pair. AWS bootstrap requires the `ubuntu` user.

The identity needs the template's EC2/network/EBS/EIP/IAM permissions, STS identity
and SSM Run Command/read permissions for the owned instance. The guest receives
only its SSM role. No administrator AWS credentials are transferred.

For selected services, also provide a Cloudflare-administered domain, a scoped DNS
token and ACME email. Enabled AWS DNS management needs a Cloudflare zone/token
even without services. Optional existing AdGuard instances need their own credentials;
see [DNS configuration and transport security](bootstrap-dns.md).
With `services: []` and DNS disabled, domain/TLS settings and service credentials
are unnecessary. AWS credentials, SSH access and storage safeguards still apply.

## Initialize

```bash
task bootstrap:init TARGET=aws
```

Initialization fills `aws.expected_account_id` from `aws sts get-caller-identity`
and `aws.admin_source_address` from this controller's public IPv4 plus `/32`.
The public SSH key is referenced by path under `vm`, not copied into source YAML.
It validates the selected public key, reads no private key and creates no AWS
resources. To select a different existing key when initializing a new source:

```bash
task bootstrap:init TARGET=aws BOOTSTRAP_SSH_PUBLIC_KEY=~/.ssh/my-aws-key.pub
```

The selected public-key path and corresponding private-key path are written to new
`bootstrap.yaml` inputs. Existing source key paths are preserved. Initialization
fills only the exact account/CIDR placeholders. Configured values and all
other edits remain untouched. Subsequent runs with no placeholders need neither
AWS credentials nor IP detection. Detection failures stop with placeholders intact;
fix credentials, networking or the key path and rerun initialization.

Pass `TARGET=aws` on every target-selecting command. If using a custom
`BOOTSTRAP_CONFIG_DIR=config/<deployment>`, pass it on initialization and every
subsequent command. Always use the original directory/backend to resume resources.

## Edit and inspect configuration

Privately edit only `config/bootstrap-aws/bootstrap.yaml`, including `secrets`.
Native Ansible and Terraform inputs are generated under `generated/` when commands run.
Never edit those generated files.
Follow [inputs and safety](bootstrap-configuration.md), then review:

- `aws.expected_account_id`, `aws.aws_region`, `aws.admin_source_address` and
  `vm.ssh_public_key`/`vm.ssh_private_key`.
- The ordered `roles` list and selected `services`, including their
  [conditional settings and credentials](bootstrap-configuration.md#selecting-host-roles-and-applications).
- For services: a published `host.repository_ref`, ACME email and dedicated
  deployment subdomain, not the homelab's existing base/wildcard.
- When selecting `debian_docker_host`: `host.docker_volumes` below `/storage/`.

Replace required placeholders privately, then inspect only allowlisted settings:

```bash
task bootstrap:show-config TARGET=aws
```

## Plan, apply and initialize storage

### Plan and review

```bash
task bootstrap:plan TARGET=aws
```

Plan uses the canonical Terraform root with a dedicated backend, native variable
validation, the AWS provider account guard and provider-data preconditions. It
checks configured DNS credentials/conflicts before provisioning. Review the normal
Terraform plan, especially any replacement, deletion or newly selected AMI. Pin
`aws.ami_id` if future plans must retain the same image. Input and saved-plan
fingerprints prevent applying changed inputs without a new reviewed plan.

### Apply and initialize storage

```bash
task bootstrap:apply TARGET=aws
```

Approve only the reviewed plan. Apply uses that **saved plan**, never silently
creates another, then configures selected roles/services and runs acceptance checks.

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

Existing whole-disk ext4 is mounted without formatting. Other filesystems,
partitioned disks and unrecognized signatures stop configuration for review.
A one-time controller marker is written before the native filesystem module runs;
an interrupted attempt cannot silently authorize another format. Never delete that
marker to retry formatting. Verification never formats storage.
The mount must match the EBS identity before Docker runs;
cloud-init also installs Docker's `/storage` mount prerequisite.

## Verify acceptance

Run the independent verification command after apply:

```bash
task bootstrap:verify TARGET=aws
```

Every deployment checks authenticated access, matching guest facts and the owned
storage mount. Selected services additionally check controller DNS, trusted HTTPS,
persistent certificate/log paths and stable containers without recreation on
repeat Compose deployment. Homepage also checks its live Traefik widget.
Host-only verification runs no Docker or application checks; it does not establish
readiness of workloads installed by custom roles.

Verification never provisions, applies roles, formats storage or rewrites DNS.
A repeat `bootstrap:plan` should show no infrastructure changes; run it only
within approved scope. Review unexpected creates/replacements; do not apply them.

## Recovery and updates

Correct the reported cause before explicitly resuming an existing guest:

```bash
task bootstrap:configure TARGET=aws
task bootstrap:verify TARGET=aws
```

`configure` does not provision or restart an instance. A stopped instance needs
separate lifecycle approval. For published repository updates, follow
[revision handling](bootstrap-configuration.md#repository-revisions-and-configuration-updates).

Do not discard state, replace host trust, force formatting or run standalone
`aws-vm:*` tasks against this backend. Cloud-init changes do not rerun on an existing
guest. If infrastructure inputs change, create and review a new plan.

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
controller artifacts removed. Private `bootstrap.yaml` and generated inputs are
retained. Keep DNS provider settings and cleanup credentials available even when
services or DNS management have been disabled.
If post-destroy verification or DNS cleanup fails, recovery files remain. Correct
the cause and retry cleanup without replaying the saved destroy plan:

```bash
task bootstrap:destroy-cleanup TARGET=aws
```

Use the same `BOOTSTRAP_CONFIG_DIR` if you selected a custom directory. Never use
fresh state as a cleanup shortcut. Operator backups, snapshots and manual DNS are
outside Terraform's ownership and may need separately approved cleanup or remain
billable.
