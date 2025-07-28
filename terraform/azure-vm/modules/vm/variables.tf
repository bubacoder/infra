# --- Common & values from dependent modules ---

variable "location" {
  description = "Location of the resources"
  type        = string
}

variable "resourcegroup" {
  description = "Name of Resource Group"
  type        = string
}

variable "subnet_id" {
  description = "ID of the subnet"
  type        = string
}

variable "data_disk_id" {
  description = "ID of the permanent data disk"
  type        = string
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
  description = "Name of the administrative user on the VM"
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
# Also: https://documentation.ubuntu.com/azure/azure-how-to/instances/find-ubuntu-images/
variable "vm_ubuntu_server_offer" {
  default     = "ubuntu-24_04-lts"
  description = "Offer of the VM"
  type        = string
}

# List of available values: az vm image list-skus -p "Canonical" -l "<location>" -f "ubuntu-24_04-lts" --output table
variable "vm_ubuntu_server_sku" {
  default     = "server"
  description = "SKU of the VM"
  type        = string
}

variable "admin_source_address" {
  description = "Allow connections (SSH, ...) only from this IP"
  type        = string
}

variable "key_vault_id" {
  description = "Id of the Azure Key Vault containing the git credentials"
  type        = string
  sensitive   = true
}

variable "git_credentials_secret_id" {
  description = "Id of the git credentials secret"
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
