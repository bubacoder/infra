locals {
  secrets_manager_name = "homeinfra-${random_id.suffix.hex}"
  
  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = "HomeInfra"
  }
}

resource "random_id" "suffix" {
  byte_length = 8
}