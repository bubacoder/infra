# AWS Bootstrap Validation — 2026-10-14

## Scope

A disposable on-demand `t3.small` Ubuntu 26.04 instance in `eu-central-1`, with
a 20 GiB root volume, 30 GiB encrypted persistent EBS volume, Elastic IP, and
SSH/HTTPS restricted to the administrator's public `/32`.

No commits or pushes were performed. The local branch was unpublished and the
checkout contained uncommitted changes, so the normal bootstrap repository guard
correctly refused it. Integration testing used the public default branch as a
clone base, then transferred the approved working-tree snapshot over
SSM-authenticated SSH and verified every source-file hash. Production revision
checks were not weakened.

The Proxmox bootstrap configuration and existing inventory were left untouched.
An isolated controller snapshot held the test inventory and service secrets.
A named temporary hosts block bypassed the existing LAN DNS wildcard for only
the four AWS test names; no public A records were created.

## Passed live checks

- AWS account/permissions, official AMI and instance architecture checks.
- Initial create-only plan and safe resume after a partial apply.
- EC2 health, SSM registration, cloud-init and authenticated SSH host-key trust.
- One-time initialization of the exact fresh, snapshot-free EBS volume.
- Recovery from an interrupted format/mount without a second format.
- Strict Ansible host limit, host configuration, Docker and Task prerequisites.
- Working-tree source hashes and private service configuration transfer.
- Docker bridge DNS and outbound HTTPS connectivity.
- Traefik/Homepage deployment and trusted Let's Encrypt HTTPS for both routes.
- Stable containers and repeat Docker deployment without container recreation.
- Persistent storage, unchanged instance/EIP/volume identities after user-data
  maintenance, and post-maintenance service acceptance.
- A repeat Terraform plan with no infrastructure changes.
- Exact SSH/HTTPS security-group CIDRs and a blocked HTTPS attempt from the VM's
  public IP, outside the administrator CIDR.
- Automatic ACME cleanup of both temporary challenge names.

## Issues found and fixed

1. **Unicode SSH comments:** EC2 rejects non-ASCII public-key comments. Register
   only the key type and encoded material, without modifying the operator's key.
2. **Fresh encrypted EBS contents:** an all-zero byte scan rejected a newly
   created, unformatted encrypted volume. External bootstrap now uses an approved
   volume-create action and a one-time private initialization receipt, validating
   identity, ownership, snapshot-free origin, attachment and absent signatures.
   Previously initialized or corrupted volumes are never automatically reformatted.
3. **Cloud-init error propagation:** independent runcmd entries could hide an
   earlier failure. External preparation now runs in one strict `bash -ec` command.
4. **Application allowlist:** existing LAN-only middleware returned 403 to the
   public administrator IP. AWS bootstrap adds exactly its validated admin CIDR;
   other deployments retain a loopback default for the additional entry.

Regression tests cover the fixes. Mocked Terraform tests cover standalone mode,
external mode and Unicode comments without contacting AWS.

Final local checks passed: 204 Python tests, 3 mocked Terraform tests, Terraform
validation/formatting, Ruff and YAML lint. Proxmox bootstrap shell tests also passed.

## Disposal

The user explicitly approved disposal, including the test data volume. The EBS
guard was removed only in the isolated runtime copy, not the tracked template.
The destroy plan was checked against the approved test resource addresses.

Verified removed: EC2 instance (terminated), root and data volumes, Elastic IP,
VPC, IAM role/profile and SSH key pair. Terraform-managed dependent resources
were destroyed with the same isolated state. The temporary hosts block was
removed and the original hosts-file hash matched exactly. Temporary controller
copies of the Cloudflare token were deleted; the original configuration was
preserved.

The isolated Terraform state has no remaining managed resources; neither test
volume has remaining snapshots. The tracked production EBS guard remains enabled,
and the local Git HEAD is unchanged.

## Remaining validation boundary

This validates the provisioning and shared deployment stages using approved
uncommitted code. A fresh run through the normal `bootstrap:plan`/`bootstrap:apply`
entry points still requires a clean checkout on a pushed branch, after commit
approval. The final cloud-init preparation shape has regression/mocked coverage;
the live VM used explicit maintenance for fixes discovered during its initial boot.
