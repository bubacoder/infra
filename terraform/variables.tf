variable "location" {
  default     = "westeurope"
  description = "Location of the resources"
  type        = string
}

variable "resourcegroup" {
  default     = "HomeInfra"
  description = "Name of Resource Group"
  type        = string
}

variable "admin_source_address" {
  description = "Allow admin access only from this IP"
  type        = string
}

variable "admin_user" {
  description = "Name of the adminustrative user on the VM"
  default     = "azureuser"
  type        = string
}

variable "git_credentials" {
  description = "Git credentials for accessing the infrastructure repository. Will be written to ~/.git-credentials"
  type        = string
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
