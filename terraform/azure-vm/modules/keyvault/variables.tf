# --- Common ---

variable "location" {
  description = "Location of the resources"
  type        = string
}

variable "resourcegroup" {
  description = "Name of Resource Group"
  type        = string
}

# --- Key Vault ---

variable "key_vault_name" {
  description = "Name of the Azure Key Vault"
  type        = string
}

variable "git_credentials" {
  description = "Git credentials for accessing the infrastructure repository"
  type        = string
  sensitive   = true
}
