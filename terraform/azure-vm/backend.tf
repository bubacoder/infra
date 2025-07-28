terraform {
  backend "local" {
    path = "../config/terraform/terraform.tfstate"
  }
}
