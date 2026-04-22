# AWS VM Terraform Variable Configuration
# Copy this file to config/terraform/aws-vm/infra.tfvars and customise.
# Variables injected automatically by Taskfile (admin_source_address, repo_url)
# do not need to be set here.
# Note: git credentials are stored in AWS Secrets Manager (not in Terraform state).
# After first apply, populate the secret: task aws-vm:secrets-info

# --- Region & Architecture ---
aws_region   = "eu-central-1"
architecture = "x86_64" # or "arm64" for Graviton (better price/performance)

# instance_type = "t3.small"  # Override the default for the selected architecture

# --- VM ---
vm_name    = "nest"
admin_user = "ubuntu"

# --- Storage ---
os_disk_size_gb   = 20
data_disk_size_gb = 10

# --- Repository ---
repo_directory = "infra"
