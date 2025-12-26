terraform {
  backend "azurerm" {
    resource_group_name  = "HomeInfra"
    storage_account_name = "tfstateinfrandomanimal" # CUSTOMIZE: Must match STORAGE_ACCOUNT_NAME in Taskfile.yaml
    container_name       = "azure-vm-state"
    key                  = "azure-vm.tfstate"
    use_oidc             = true
    use_azuread_auth     = true
  }
}
