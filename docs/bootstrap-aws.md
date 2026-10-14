# Bootstrap on AWS

The AWS target reuses `terraform/aws-vm` to create an Ubuntu EC2 Docker host,
then uses the same separate-admin-host Ansible and core Docker deployment as
Proxmox. The stages have unit, mocked Terraform and disposable live AWS validation.
See [validation results and remaining boundaries](bootstrap-aws-validation.md)
before treating the complete workflow as production-ready.

## Supported profile

- Fresh, on-demand x86_64 Ubuntu instance with EBS NVMe support in a public subnet
  (for example, `t3.small`). Legacy non-NVMe instance types are rejected during preflight.
- Stable Elastic IP and persistent encrypted EBS volume mounted at `/storage`.
- SSH and HTTPS restricted to your administrator public IPv4 CIDR.
- Traefik and Homepage, using Cloudflare DNS-01 certificates.
- External DNS management. No automatic adoption of existing AWS deployments,
  Spot instances, ARM instances, private subnets, or teardown.

AWS charges apply to EC2, EBS and public IPv4/Elastic IP. Stopping EC2 does not
stop all charges. Failed deployments and DNS checkpoints leave resources intact.

## Prerequisites

Use a Linux administrative host with the shared tools listed in [setup](setup.md),
plus Terraform >= 1.5, AWS CLI, and `ssh-keygen`. The offline Terraform tests need
Terraform >= 1.7 because they use mock providers.

Configure AWS credentials through the standard credential chain, preferably an
AWS profile/SSO. Bootstrap never asks for or stores AWS access keys in YAML.
The authenticated account must match `aws.account_id`.

The provisioning identity needs permissions for the template's EC2/VPC/EBS/EIP,
security groups, key pair and IAM instance-role/profile resources, including
passing the instance role. Preflight also needs STS identity, EC2 image/type/tag
reads and IAM role/instance-profile listing. Guest readiness and SSH trust use Systems Manager
Run Command: allow SendCommand for `AWS-RunShellScript` on the owned instance,
GetCommandInvocation and DescribeInstanceInformation. The guest receives SSM
managed-instance permissions, not the administrator's AWS credentials.

Provide an existing public SSH key with a usable matching private key or agent
identity. Keep the private key mode 0600 or stricter. The initial profile requires
the `ubuntu` account. Ensure the admin host's public IP is inside the configured
CIDR; VPN/NAT changes can otherwise block access.

Bootstrap also supplies this same administrator CIDR to Traefik's application
allowlist. Other deployments keep the existing private-network policy; the extra
allowlist entry defaults to loopback when no cloud administrator CIDR is supplied.

Use a public domain in Cloudflare and the same `Zone:Read`/`DNS:Edit` token and
ACME email as the Proxmox profile. Keep the repository clean and pushed at the
selected branch tip, so the guest can check out the exact same revision. A public,
guest-accessible HTTPS repository is required and is checked without local Git
credentials. GitHub SSH origins are normalized to HTTPS; private repository
authentication is not added by this AWS bootstrap profile.

## Configure and plan

```bash
task bootstrap:init TARGET=aws
```

This creates `config/bootstrap.yaml` with mode 0600 from
`config-example/bootstrap-aws.yaml`. It never overwrites an existing file.
If a Proxmox bootstrap configuration already exists, preserve it and create a
separate mode-0600 AWS configuration under `config/`; use `CONFIG=<path>` on plan
and apply to select it.

Edit the account ID, region/profile, host name, SSH key, administrator CIDR,
domain and TLS settings. The documentation IP/CIDR is deliberately not usable.
Docker volumes must be beneath `/storage`, for example `/storage/docker-volumes`.

```bash
task bootstrap:plan
```

Planning checks account and SSH identity, public IP access, official AMI,
instance architecture and EBS NVMe support, resource ownership and Terraform actions. It initializes
providers and writes private local artifacts, but does not apply cloud changes.
Before apply starts and while no Terraform state exists, each plan refreshes the
AMI and provisioning inputs in the deployment manifest. You can edit the configuration
or update templates and replan without deleting local artifacts. Once apply starts
or state exists, the manifest is frozen so retries cannot silently select a newer
image or change cloud-init.

Bootstrap's AWS state is separate from standalone `task aws-vm:*` state:

```text
config/terraform/bootstrap/<hostname>/
├── manifest.json
├── known_hosts                 # Written only after trusted SSM verification
└── runtime/
    ├── bootstrap.tfvars.json
    ├── bootstrap.tfplan
    ├── terraform.tfstate
    ├── .terraform.lock.hcl
    └── ...canonical template files and provider/module cache
```

Do not run standalone AWS tasks against this deployment. Keep state and its
backups private and backed up. Never discard state to resolve a deployment error.
The runtime template copy is generated from tracked code; do not edit it manually.

## Apply and DNS checkpoint

```bash
task bootstrap:apply
```

Apply refreshes the plan, displays account/region and cost-bearing changes, asks
for confirmation, and applies that exact saved plan. `YES=1` only skips the
confirmation; it does not bypass safety checks.

Bootstrap waits for EC2 health, SSM registration and successful cloud-init,
initializes a newly created EBS volume once, verifies its mount, and retrieves SSH host public keys through authenticated
SSM before trusting the network SSH key. It does not fall back to trust-on-first-use.
A matching owned instance that was stopped is started after apply approval;
terminated or otherwise conflicting resources are never automatically replaced.

First-time formatting requires an approved Terraform volume-create action and a
private initialization receipt. The controller verifies the exact volume ID,
snapshot-free origin, ownership tag, attachment and absent filesystem/signatures.
It records the attempt before formatting. A retry can mount an existing ext4
filesystem, but cannot automatically reformat a corrupted or previously initialized
volume. Raw encrypted EBS bytes are not assumed to be all zeroes.

The first apply normally stops at an AWS DNS checkpoint and reports the Elastic
IP. Point the base domain and wildcard to that IP using **DNS-only** records,
not Cloudflare-proxied records. Confirm the admin host resolves the base domain,
`home`, `traefik` and `bootstrap-check` names to that single IPv4 address.
Then rerun the same apply command.

There is no DHCP reservation or `/etc/hosts` requirement for AWS. Only clients
permitted by the security group can access HTTPS. DNS-01 does not require inbound
port 80.

After DNS verification, bootstrap renders shared inventory and Docker configuration,
limits Ansible to the new host, clones the pinned repository, transfers the
Cloudflare token over trusted SSH, and deploys the core services. Acceptance checks
cover HTTPS, container stability, EBS persistence, repeat Docker apply, and a
repeat Terraform plan without changes.

## Recovery and safety

Correct the reported issue and rerun the same apply. Resources and state remain
intact at checkpoints. Missing state after apply began, different provisioning
inputs/template, conflicting names, SSH key changes, deletion/replacement plans,
or EBS attachment changes stop for manual inspection.

Changing cloud-init on an existing instance does not rerun it. Provisioning-input
changes require an explicitly reviewed maintenance workflow outside bootstrap.
Cloudflare tokens never enter Terraform state, EC2 user data or SSM commands.

If SSM does not register, inspect EC2 cloud-init through the AWS console and check
SSM Agent installation, instance role permissions and outbound HTTPS reachability.
If the data mount failed, do not start Docker on root storage; the external
cloud-init profile also installs a Docker systemd mount prerequisite.

Teardown is separate and must be explicitly approved. The data volume has
`prevent_destroy`, so a blanket Terraform destroy is refused rather than deleting
data. Bootstrap never deletes an existing VM, volume, or persistent service data.
