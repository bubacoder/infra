terraform {
  backend "local" {
    path = "../../config/terraform/azure-vm/terraform.tfstate"
  }
}
