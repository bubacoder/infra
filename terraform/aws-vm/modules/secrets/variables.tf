variable "region" {
  description = "AWS region"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "secrets_manager_name" {
  description = "Name for the AWS Secrets Manager"
  type        = string
}

variable "git_credentials" {
  description = "Git credentials for accessing the infrastructure repository"
  type        = string
  sensitive   = true
}