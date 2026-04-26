# AWS VM — Terraform

Deploys an Ubuntu 24.04 LTS EC2 instance on AWS with:
- x86_64 or ARM64 (Graviton) architecture selection
- Persistent EBS data volume that survives instance termination
- Secrets Manager + IAM Instance Profile for credential-less secret retrieval
- Cloud-init bootstrap → Ansible configuration

Uses the [terraform-aws-modules](https://github.com/terraform-aws-modules/) community collection to minimise custom code.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  VPC (10.0.0.0/16)                              │
│  ┌──────────────────────────────────────────┐   │
│  │  Public Subnet (10.0.1.0/24)             │   │
│  │  ┌────────────────────────────────────┐  │   │
│  │  │  EC2 Instance                      │  │   │
│  │  │  - Ubuntu 24.04 LTS                │  │   │
│  │  │  - IAM Instance Profile            │  │   │
│  │  │  - gp3 root volume                 │  │   │
│  │  │  - EBS data volume (/storage)      │  │   │
│  │  └────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────┘   │
│  Security Group: SSH/HTTPS from admin IP only   │
└─────────────────────────────────────────────────┘
         │
         ▼
Internet Gateway → Public IP

AWS Secrets Manager: git credentials (IAM role access)
```

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured with credentials
- [Task](https://taskfile.dev/installation/) task runner
- [tfsec](https://github.com/aquasecurity/tfsec) (optional, for `check` task)
- [terraform-docs](https://terraform-docs.io/) (optional, for `docs` task)

## Setup

### 1. Configure AWS credentials

```bash
aws configure
# or use AWS_PROFILE / AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars
# or use IAM Identity Center: aws sso login
```

### 2. Create the variable file

```bash
mkdir -p config/terraform/aws-vm
cp config-example/terraform/aws-vm/infra.tfvars config/terraform/aws-vm/infra.tfvars
# Edit config/terraform/aws-vm/infra.tfvars
```

### 3. Prepare git credentials

The Taskfile reads `~/.git-credentials` automatically. If you use a GitHub PAT:
```
https://<username>:<token>@github.com
```

### 4. Deploy

```bash
task aws-vm:apply
```

This will:
1. Fetch your public IP and inject it as the SSH/HTTPS source
2. Read git credentials from `~/.git-credentials`
3. Create all AWS resources
4. Write the SSH private key to `~/.ssh/id_rsa_aws_vm`

### 5. Connect

```bash
task aws-vm:connect-vm
```

## Tasks

| Task                        | Description                                 |
| --------------------------- | ------------------------------------------- |
| `task aws-vm:plan`          | Create Terraform plan                       |
| `task aws-vm:apply`         | Apply plan + save SSH key                   |
| `task aws-vm:destroy`       | Destroy all resources                       |
| `task aws-vm:destroy-vm`    | Destroy EC2 instance only (keeps EBS)       |
| `task aws-vm:connect-vm`    | SSH into VM                                 |
| `task aws-vm:config-vm`     | Run Ansible on VM                           |
| `task aws-vm:start-vm`      | Start instance                              |
| `task aws-vm:stop-vm`       | Stop instance                               |
| `task aws-vm:secrets-info`  | Show Secrets Manager retrieval instructions |
| `task aws-vm:migrate-state` | Migrate state to S3 backend                 |
| `task aws-vm:check`         | Validate + security scan                    |

> **Cloud-init caveat:** `user_data_replace_on_change = false` in `main.tf` means Terraform will **not** re-run cloud-init when the cloud-init templates change on an existing instance. To apply updated cloud-init content, run `task aws-vm:destroy-vm` followed by `task aws-vm:apply` (the EBS data volume is preserved). Skipping this step will leave the running instance with the old bootstrap configuration.

## Architecture Selection

| Architecture | Default Type | Notes                                   |
| ------------ | ------------ | --------------------------------------- |
| `x86_64`     | t3.small     | Intel/AMD, wider software compatibility |
| `arm64`      | t4g.small    | Graviton, ~20% better price/performance |

Set in `infra.tfvars`:
```hcl
architecture = "arm64"
```

## Persistent Data Volume

The data EBS volume at `/storage` has `prevent_destroy = true`. It **survives** both `destroy-vm` and `destroy` tasks. To fully delete it:

1. Remove the `lifecycle { prevent_destroy = true }` block from `main.tf`
2. Run `task aws-vm:plan` and `task aws-vm:apply` (no instance changes, just removes the guard)
3. Run `task aws-vm:destroy`

Alternatively, delete manually:
```bash
aws ec2 delete-volume --volume-id <vol-id>
```

## Remote State Backend (optional)

For shared/CI usage, configure an S3 backend:

```bash
# Create S3 bucket (name must be globally unique)
BUCKET="my-terraform-state-$(aws sts get-caller-identity --query Account --output text)"
aws s3api create-bucket --bucket "$BUCKET" --region eu-central-1 \
    --create-bucket-configuration LocationConstraint=eu-central-1
aws s3api put-bucket-versioning --bucket "$BUCKET" \
    --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$BUCKET" \
    --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Create DynamoDB lock table
aws dynamodb create-table --table-name terraform-locks \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region eu-central-1
```

Then update `backend.tf`, uncomment the backend block with your bucket name, and run:
```bash
task aws-vm:migrate-state
terraform init -migrate-state
```

## Cloud-Init Bootstrap

At first boot the instance:
1. Upgrades packages, installs git and unzip
2. Fetches git credentials from Secrets Manager (using the instance IAM role — no login needed)
3. Clones the infrastructure repository to `~/repos/infra/`
4. Mounts the EBS data volume to `/storage` (NVMe-aware, formats on first boot)
5. Runs `ansible/bootstrap-ansible.sh` to configure the system

Monitor progress:
```bash
# SSH in and watch the log
ssh -i ~/.ssh/id_rsa_aws_vm ubuntu@<public-ip>
sudo tail -f /var/log/cloud-init-output.log
```

## Ansible Integration

After cloud-init completes, configure the Ansible inventory for the AWS VM host and run:
```bash
task aws-vm:config-vm
# or manually: cd ansible && ./apply-cloud.sh
```

## GitHub Actions (OIDC)

For CI/CD without long-lived credentials, create an IAM OIDC provider for GitHub:

```bash
# Create OIDC provider
aws iam create-open-id-connect-provider \
    --url https://token.actions.githubusercontent.com \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

Then create an IAM role with a trust policy scoped to your repo and reference it in GitHub Actions via `aws-actions/configure-aws-credentials` with `role-to-assume`.

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5 |
| aws | ~> 5.0 |
| cloudinit | ~> 2.3 |
| tls | ~> 4.0 |

## Providers

| Name | Version |
|------|---------|
| aws | ~> 5.0 |
| cloudinit | ~> 2.3 |
| tls | ~> 4.0 |

## Modules

| Name | Source | Version |
|------|--------|---------|
| ec2 | terraform-aws-modules/ec2-instance/aws | ~> 5.0 |
| key\_pair | terraform-aws-modules/key-pair/aws | ~> 2.0 |
| security\_group | terraform-aws-modules/security-group/aws | ~> 5.0 |
| vpc | terraform-aws-modules/vpc/aws | ~> 5.0 |

## Resources

| Name | Type |
|------|------|
| [aws_ebs_volume.data](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ebs_volume) | resource |
| [aws_iam_instance_profile.ec2](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_instance_profile) | resource |
| [aws_iam_role.ec2](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy.secrets_access](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_secretsmanager_secret.git_credentials](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/secretsmanager_secret) | resource |
| [aws_secretsmanager_secret_version.git_credentials](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/secretsmanager_secret_version) | resource |
| [aws_volume_attachment.data](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/volume_attachment) | resource |
| [tls_private_key.main](https://registry.terraform.io/providers/hashicorp/tls/latest/docs/resources/private_key) | resource |
| [aws_ami.ubuntu](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ami) | data source |
| [aws_availability_zones.available](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/availability_zones) | data source |
| [cloudinit_config.main](https://registry.terraform.io/providers/hashicorp/cloudinit/latest/docs/data-sources/config) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| admin\_source\_address | CIDR or IP allowed SSH and HTTPS access (e.g. your public IP: '1.2.3.4/32') | `string` | n/a | yes |
| admin\_user | SSH admin username (Ubuntu default is 'ubuntu') | `string` | `"ubuntu"` | no |
| architecture | CPU architecture: 'x86\_64' or 'arm64' (Graviton) | `string` | `"x86_64"` | no |
| aws\_region | AWS region for all resources | `string` | `"eu-central-1"` | no |
| data\_disk\_size\_gb | Persistent data EBS volume size in GB (survives instance termination) | `number` | `10` | no |
| git\_credentials | Git credentials for accessing the infrastructure repository. Will be written to ~/.git-credentials on the VM. | `string` | n/a | yes |
| instance\_type | EC2 instance type. Defaults to t3.small (x86\_64) or t4g.small (arm64) when null. | `string` | `null` | no |
| os\_disk\_size\_gb | Root OS disk size in GB | `number` | `20` | no |
| repo\_directory | Local directory name for the cloned repository | `string` | `"infra"` | no |
| repo\_url | URL of the infrastructure repository to clone | `string` | n/a | yes |
| vm\_name | Name tag and hostname of the VM | `string` | `"nest"` | no |

## Outputs

| Name | Description |
|------|-------------|
| ami\_id | AMI ID used for the instance |
| instance\_id | EC2 instance ID |
| public\_ip | Public IP address of the instance |
| public\_key\_fingerprint\_sha256 | SHA-256 fingerprint of the SSH public key |
| secrets\_manager\_secret\_name | Name of the Secrets Manager secret storing git credentials |
| ssh\_private\_key | SSH private key (ED25519) for connecting to the instance |
<!-- END_TF_DOCS -->
