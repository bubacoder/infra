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

variable "subnet_id" {
  description = "ID of the subnet"
  type        = string
}

variable "vm_size" {
  default     = "Standard_D2s_v3"
  description = "Size of the VM"
  type        = string
}

# List of available values: az vm image list-offers -p "Canonical" -l "eastus2" --output table
variable "vm_ubuntu_server_offer" {
  default     = "0001-com-ubuntu-server-jammy"
  description = "Offer of the VM"
  type        = string
}

# List of available values: az vm image list-skus -p "Canonical" -l "eastus2" -f 0001-com-ubuntu-server-jammy --output table
variable "vm_ubuntu_server_sku" {
  default     = "22_04-lts-gen2"
  description = "SKU of the VM"
  type        = string
}

variable "admin_source_address" {
  default     = "1.2.3.4"
  description = "Allow admin access only from these ports"
  type        = string
}

variable "data_disk_id" {
  description = "ID of the permanent data disk"
  type        = string
}
