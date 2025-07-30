# --- Common ---

variable "region" {
  description = "AWS region"
  default     = "eu-west-1"
  type        = string
}

variable "environment" {
  description = "Environment name"
  default     = "HomeInfra"
  type        = string
}

# --- Storage ---

variable "storage_disk_size_gb" {
  description = "Size of the permanent disk in GB"
  default     = 10
  type        = number
}

# --- Virtual Machine ---

variable "vm_name" {
  description = "Name, hostname of the VM"
  type        = string
}

variable "vm_domain_name" {
  description = "DNS name of the VM"
  type        = string
}

variable "admin_user" {
  description = "Name of the administrative user on the VM"
  default     = "ec2-user"
  type        = string
}

# Instance types: https://aws.amazon.com/ec2/instance-types/
variable "instance_type" {
  default     = "t3.medium"
  description = "EC2 instance type"
  type        = string
}

# For Ubuntu 24.04 LTS - will need to look up the AMI ID per region
variable "ami_id" {
  description = "AMI ID for Ubuntu 24.04 LTS"
  type        = string
}

variable "admin_source_address" {
  description = "Allow connections (SSH, ...) only from this IP"
  type        = string
}

variable "git_credentials" {
  description = "Git credentials for accessing the infrastructure repository. Will be stored in AWS Secrets Manager."
  type        = string
  sensitive   = true
}

variable "repo_url" {
  description = "URL of the infrastructure repository"
  type        = string
}

variable "repo_directory" {
  description = "Name of the infrastructure repository directory"
  default     = "infra"
  type        = string
}