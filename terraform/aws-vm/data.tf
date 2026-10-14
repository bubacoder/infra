# Ubuntu 24.04 LTS (Noble) AMI — official Canonical images
data "aws_ami" "ubuntu" {
  count       = var.ami_id == null ? 1 : 0
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = [local.arch_config[var.architecture].ami_pattern]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = [var.architecture]
  }
}

# Use the first available AZ in the region for the subnet and EBS volume
data "aws_availability_zones" "available" {
  state = "available"
}

# Cloud-init configuration composed from template parts
data "cloudinit_config" "main" {
  gzip          = true
  base64_encode = true

  part {
    filename     = "cloud-init.yaml"
    content_type = "text/cloud-config"
    content = var.bootstrap_mode == "external" ? templatefile("${path.module}/cloud-init/external.yaml.tpl", {
      ADMIN_USER     = var.admin_user
      HOSTNAME       = var.vm_name
      SSH_PUBLIC_KEY = local.ssh_public_key
      MOUNT_STORAGE_SCRIPT_CONTENT = templatefile("${path.module}/cloud-init/mount-storage.sh.tpl", {
        DATA_VOLUME_ID    = aws_ebs_volume.data.id
        FORMAT_NEW_VOLUME = "false"
      })
      }) : templatefile("${path.module}/cloud-init/cloud-init.yaml.tpl", {
      ADMIN_USER        = var.admin_user
      REPO_DIR          = var.repo_directory
      REPO_SETUP_SCRIPT = "/opt/repo-setup.sh"
      REPO_SETUP_SCRIPT_CONTENT = templatefile("${path.module}/cloud-init/repo-setup.sh.tpl", {
        ADMIN_USER                 = var.admin_user
        AWS_REGION                 = var.aws_region
        GIT_CREDENTIALS_SECRET_ARN = aws_secretsmanager_secret.git_credentials[0].arn
        REPO_URL                   = var.repo_url
        REPO_DIR                   = var.repo_directory
      })
      MOUNT_STORAGE_SCRIPT_CONTENT = templatefile("${path.module}/cloud-init/mount-storage.sh.tpl", {
        DATA_VOLUME_ID    = aws_ebs_volume.data.id
        FORMAT_NEW_VOLUME = "true"
      })
    })
  }
}

moved {
  from = data.aws_ami.ubuntu
  to   = data.aws_ami.ubuntu[0]
}
