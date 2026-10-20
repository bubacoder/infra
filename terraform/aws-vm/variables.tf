# --- Region & Architecture ---

variable "aws_region" {
  description = "AWS region for all resources"
  default     = "eu-central-1"
  type        = string
  validation {
    condition     = can(regex("^[a-z]{2}(-[a-z]+)+-[0-9]+$", var.aws_region))
    error_message = "aws_region must be an AWS region name."
  }
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
  validation {
    condition     = var.instance_type == null ? true : can(regex("^[a-z0-9]+(-[a-z0-9]+)*\\.[a-z0-9]+(-[a-z0-9]+)*$", var.instance_type))
    error_message = "instance_type must be a valid EC2 instance type or null."
  }
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
  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", var.vm_name))
    error_message = "vm_name must be a lowercase hostname label."
  }
}

variable "admin_user" {
  description = "SSH admin username (Ubuntu default is 'ubuntu')"
  default     = "ubuntu"
  type        = string
  validation {
    condition     = can(regex("^[a-z_][a-z0-9_-]*$", var.admin_user))
    error_message = "admin_user must be a valid Linux account name."
  }
}

variable "admin_source_address" {
  description = "CIDR or IP allowed SSH and HTTPS access (e.g. your public IP: '1.2.3.4/32')"
  type        = string

  validation {
    condition     = can(cidrnetmask(var.admin_source_address)) && !endswith(var.admin_source_address, "/0")
    error_message = "admin_source_address must be a restricted IPv4 CIDR, never /0."
  }
}

variable "k3s_api_access" {
  description = "Allow the K3s Kubernetes API from admin_source_address for external bootstrap"
  type        = bool
  default     = false
}

# --- Storage ---

variable "os_disk_size_gb" {
  description = "Root OS disk size in GB"
  default     = 20
  type        = number
  validation {
    condition     = var.os_disk_size_gb >= 8 && floor(var.os_disk_size_gb) == var.os_disk_size_gb
    error_message = "os_disk_size_gb must be an integer of at least 8 GiB."
  }
}

variable "data_disk_size_gb" {
  description = "Persistent data EBS volume size in GB (survives instance termination)"
  default     = 10
  type        = number
  validation {
    condition     = var.data_disk_size_gb > 0 && floor(var.data_disk_size_gb) == var.data_disk_size_gb
    error_message = "data_disk_size_gb must be a positive integer."
  }
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
    condition     = var.ssh_public_key == null ? true : can(regex("^(ssh-ed25519|ssh-rsa|ecdsa-sha2-[^ ]+) [A-Za-z0-9+/]+={0,3}( .*)?$", var.ssh_public_key))
    error_message = "ssh_public_key must be null or a usable SSH public key."
  }
}

variable "ami_id" {
  description = "Pinned official Ubuntu AMI; null selects the most recent release"
  type        = string
  default     = null
  validation {
    condition     = var.ami_id == null ? true : can(regex("^ami-[0-9a-f]+$", var.ami_id))
    error_message = "ami_id must be an AMI ID or null."
  }
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
