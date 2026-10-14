# --- Region & Architecture ---

variable "aws_region" {
  description = "AWS region for all resources"
  default     = "eu-central-1"
  type        = string
}

variable "expected_account_id" {
  description = "Optional account guard; bootstrap always supplies its expected AWS account"
  type        = string
  default     = null
  validation {
    condition     = var.expected_account_id == null ? true : can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id must be null or a 12-digit AWS account ID."
  }
}

# Browse available Ubuntu AMIs: https://cloud-images.ubuntu.com/locator/ec2/
variable "ubuntu_version" {
  description = "Ubuntu release string used in the AMI name (e.g. 'ubuntu-resolute-26.04', 'ubuntu-noble-24.04')"
  default     = "ubuntu-resolute-26.04"
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

variable "spot_instance" {
  description = "Use a Spot instance instead of On-Demand. Reduces cost by ~70% but the instance may be interrupted."
  default     = false
  type        = bool
}

variable "spot_price" {
  description = "Maximum spot bid price (USD/hr). null = on-demand price cap (recommended — avoids accidental overbidding)."
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
  default     = ""
}

variable "bootstrap_mode" {
  description = "Standalone guest setup or external administrative-host orchestration"
  type        = string
  default     = "standalone"
  validation {
    condition     = contains(["standalone", "external"], var.bootstrap_mode)
    error_message = "bootstrap_mode must be standalone or external."
  }
}

variable "ssh_public_key" {
  description = "Existing public SSH key; null preserves standalone generated-key behavior"
  type        = string
  default     = null
  validation {
    condition     = var.ssh_public_key == null ? true : startswith(var.ssh_public_key, "ssh-ed25519 ") || startswith(var.ssh_public_key, "ssh-rsa ") || startswith(var.ssh_public_key, "ecdsa-")
    error_message = "ssh_public_key must be null or a usable SSH public key."
  }
}

variable "ami_id" {
  description = "Pinned official Ubuntu AMI; null selects the most recent release"
  type        = string
  default     = null
}

variable "allocate_elastic_ip" {
  description = "Allocate a stable public IPv4 address"
  type        = bool
  default     = false
}

variable "repo_directory" {
  description = "Local directory name for the cloned repository"
  default     = "infra"
  type        = string
}
