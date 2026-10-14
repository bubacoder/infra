# AWS Bootstrap Validation — 2026-10-14

## Initial stage test (before commit approval)

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

Final local checks passed: 208 Python tests, 3 mocked Terraform tests, Terraform
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

## Published-branch CLI validation

After commit/push approval, a second fresh target used the normal public commands
from a clean checkout on the pushed `aws-bootstrap` branch:

```bash
task bootstrap:plan CONFIG=config/bootstrap-aws-cli-test.yaml
task bootstrap:apply CONFIG=config/bootstrap-aws-cli-test.yaml YES=1
```

The first apply completed fresh cloud-init, one-time EBS formatting and SSH trust,
then reached the expected operator DNS checkpoint. A named temporary hosts mapping
was added for the test names and the same apply command resumed the deployment.
No working-tree overlay, alternate runner or repository-guard bypass was used.

This round found and fixed two additional issues:

- **Ownership on resume:** EC2 tags expose the root volume separately, although
  Terraform manages it inside the instance's nested root-device state. Include
  those controlled volume IDs and match the template's actual IAM profile name.
  Fix: `f41a42d`.
- **Dashboard widget routing:** Homepage resolved the public Traefik hostname back
  to the LAN server. Give Traefik its hostname as a private Docker network alias,
  preserving hostname/SNI and trusted TLS without widening the security group.
  Acceptance now checks the widget's live API statistics, not only HTML pages.
  Fix: `869d389`.

Fresh deployment and full repeat applies passed through the production CLI.
Instance, Elastic IP and data-volume identities remained unchanged; Docker repeat
deployment did not recreate containers, and the repeat Terraform plan was clean.
Both HTTPS routes and the Traefik widget passed. A non-admin public-IP HTTPS
request was blocked and ACME left no temporary challenge records.

The second target was fully disposed of after testing: instance, both volumes,
Elastic IP, VPC, IAM role/profile and SSH key pair were verified removed. Docker
was stopped and the data filesystem unmounted before teardown. The original
inventory was restored byte-for-byte, the hosts-file hash matched its baseline,
and the Proxmox bootstrap configuration was unchanged. Temporary copies of the
test service token and bootstrap configuration were deleted.

Gitleaks, AWS-credential/private-key detection and YAML pre-commit checks passed.
No hosted workflow runs were triggered by these branch pushes; local and live
checks were used instead.

The initial implementation was committed as `b2b523c`; all implementation and fix
commits were pushed to `aws-bootstrap`. This validates the full documented CLI
flow for the supported public, on-demand x86_64 core profile. Other profiles listed
as unsupported in the AWS guide remain outside the tested scope.
