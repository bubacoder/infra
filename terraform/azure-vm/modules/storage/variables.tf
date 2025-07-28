variable "location" {
  description = "Location of the resources"
  type        = string
}

variable "resourcegroup" {
  description = "Name of Resource Group"
  type        = string
}

variable "disk_size_gb" {
  description = "Size of the permanent disk in GB"
  type        = number
}
