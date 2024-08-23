# --- Common ---

variable "subscription_id" {
  description = "Azure subscription ID (format: '00000000-xxxx-xxxx-xxxx-xxxxxxxxxxxx')"
  type        = string
}

variable "location" {
  description = "Location of the resources"
  default     = "westeurope"
  type        = string
}

variable "resourcegroup" {
  description = "Name of Resource Group"
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

variable "vm_domain_name_label" {
  description = "DNS name of the VM. The FQDN will be: <vm_domain_name_label>.<location>.cloudapp.azure.com"
  type        = string
}

variable "admin_user" {
  description = "Name of the adminustrative user on the VM"
  default     = "azureuser"
  type        = string
}

# VM sizes: https://azure.microsoft.com/en-us/pricing/details/virtual-machines/series/
# Compare prices: https://cloudprice.net/
variable "vm_size" {
  default     = "Standard_D2s_v5"
  description = "Size of the VM"
  type        = string
}

# List of available values: az vm image list-offers -p "Canonical" -l "<location>" --output table
variable "vm_ubuntu_server_offer" {
  default     = "0001-com-ubuntu-server-jammy"
  description = "Offer of the VM"
  type        = string
}

# List of available values: az vm image list-skus -p "Canonical" -l "<location>" -f 0001-com-ubuntu-server-jammy --output table
variable "vm_ubuntu_server_sku" {
  default     = "22_04-lts-gen2"
  description = "SKU of the VM"
  type        = string
}

variable "admin_source_address" {
  description = "Allow connections (SSH, ...) only from this IP"
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
