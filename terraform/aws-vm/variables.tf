# --- Region & Architecture ---

variable "aws_region" {
  description = "AWS region for all resources"
  default     = "eu-central-1"
  type        = string
}

# Instance types by architecture:
#   x86_64: t3.small (2 vCPU, 2 GB RAM) — general-purpose, Intel/AMD
#   arm64:  t4g.small (2 vCPU, 2 GB RAM) — Graviton, better price/performance
# Compare prices: https://cloudprice.net/ or https://instances.vantage.sh/
variable "architecture" {
  description = "CPU architecture: 'x86_64' or 'arm64' (Graviton)"
  default     = "x86_64"
  type        = string

  validation {
    condition     = contains(["x86_64", "arm64"], var.architecture)
    error_message = "architecture must be 'x86_64' or 'arm64'."
  }
}

variable "instance_type" {
  description = "EC2 instance type. Defaults to t3.small (x86_64) or t4g.small (arm64) when null."
  default     = null
  type        = string
}

# --- VM ---

variable "vm_name" {
  description = "Name tag and hostname of the VM"
  default     = "nest"
  type        = string
}

variable "admin_user" {
  description = "SSH admin username (Ubuntu default is 'ubuntu')"
  default     = "ubuntu"
  type        = string
}

variable "admin_source_address" {
  description = "CIDR or IP allowed SSH and HTTPS access (e.g. your public IP: '1.2.3.4/32')"
  type        = string

  validation {
    condition     = can(cidrnetmask(var.admin_source_address))
    error_message = "admin_source_address must be valid CIDR notation (e.g. '1.2.3.4/32')."
  }
}

# --- Storage ---

variable "os_disk_size_gb" {
  description = "Root OS disk size in GB"
  default     = 20
  type        = number
}

variable "data_disk_size_gb" {
  description = "Persistent data EBS volume size in GB (survives instance termination)"
  default     = 10
  type        = number
}

# --- Repository ---

variable "repo_url" {
  description = "URL of the infrastructure repository to clone"
  type        = string
}

variable "repo_directory" {
  description = "Local directory name for the cloned repository"
  default     = "infra"
  type        = string
}
