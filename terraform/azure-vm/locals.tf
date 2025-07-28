resource "random_string" "keyvault_suffix" {
  length  = 6
  upper   = false
  special = false
}

locals {
  keyvault_name = "infra-keyvault-${random_string.keyvault_suffix.result}"
}
