variable "region" {
  description = "AWS region"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "disk_size_gb" {
  description = "Size of the data disk in GB"
  type        = number
}