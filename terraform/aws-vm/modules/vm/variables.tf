variable "region" {
  description = "AWS region"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "subnet_id" {
  description = "ID of the subnet where the VM will be created"
  type        = string
}

variable "ebs_volume_id" {
  description = "ID of the EBS volume to attach to the VM"
  type        = string
}

variable "vm_name" {
  description = "Name of the virtual machine"
  type        = string
}

variable "vm_domain_name" {
  description = "Domain name for the VM"
  type        = string
}

variable "admin_user" {
  description = "Name of the administrative user on the VM"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
}

variable "ami_id" {
  description = "AMI ID to use for the VM"
  type        = string
}

variable "admin_source_address" {
  description = "IP address from which admin connections are allowed"
  type        = string
}

variable "secrets_manager_arn" {
  description = "ARN of the Secrets Manager"
  type        = string
}

variable "git_credentials_secret_id" {
  description = "Secret ID for Git credentials"
  type        = string
}

variable "repo_url" {
  description = "URL of the infrastructure repository"
  type        = string
}

variable "repo_directory" {
  description = "Name of the infrastructure repository directory"
  type        = string
}