# Terraform/OpenTofu

**Terraform**

> Infrastructure automation to provision and manage resources in any cloud or data center.

Home: https://www.terraform.io/  
Releases: https://github.com/hashicorp/terraform/releases  
Final version with *Mozilla Public License*: 1.5.7  
The newer versions are released under *Business Source License*.  

**OpenTofu**

> The open source infrastructure as code tool

Home: https://opentofu.org/  
Releases: https://github.com/opentofu/opentofu/releases  

## Basic Terraform commands - Cheat sheet

| Command                         | Description                                                                                 |
| ------------------------------- | ------------------------------------------------------------------------------------------- |
| `terraform init`                | Initialize the Terraform directory and download the required provider plugins               |
| `terraform fmt -recursive`      | Ensure all Terraform code in the current directory and subdirectories is formatted properly |
| `terraform validate`            | Validate the syntax of the Terraform configuration files and check for errors               |
| `terraform plan`                | Show the execution plan, the resources that will be created, updated, or destroyed          |
| `terraform apply`               | Apply the changes required to reach the desired state of the infrastructure                 |
| `terraform destroy`             | Destroy the Terraform-managed infrastructure                                                |
| `terraform show`                | Display the current state of the Terraform-managed infrastructure                           |
| `terraform state list`          | List all resources in the Terraform state                                                   |
| `terraform apply -replace "id"` | Force replacement of a resource                                                             |

## Azure VM module

The modules in the `terraform/modules` folder are implementing a Virtual Machine with the associated network setup and storage.
This VM can be used to test/host the Docker services of this repo.

**Usage:**

1. Login to Azure account (without browser access on device): `az login --use-device-code`
2. See the file `terraform/Makefile` for available `make` commands for deploying/connection/deleting the VM.

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5 |
| azurerm | ~> 4.0 |

## Modules

| Name | Source | Version |
|------|--------|---------|
| base | ./modules/base | n/a |
| storage | ./modules/storage | n/a |
| vm | ./modules/vm | n/a |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| admin\_source\_address | Allow connections (SSH, ...) only from this IP | `string` | n/a | yes |
| admin\_user | Name of the administrative user on the VM | `string` | `"azureuser"` | no |
| git\_credentials | Git credentials for accessing the infrastructure repository. Will be written to ~/.git-credentials | `string` | n/a | yes |
| location | Location of the resources | `string` | `"westeurope"` | no |
| repo\_directory | Name of the infrastructure repository directory | `string` | `"infra"` | no |
| repo\_url | URL of the infrastructure repository | `string` | n/a | yes |
| resourcegroup | Name of Resource Group | `string` | `"HomeInfra"` | no |
| storage\_disk\_size\_gb | Size of the permanent disk in GB | `number` | `10` | no |
| subscription\_id | Azure subscription ID (format: '00000000-xxxx-xxxx-xxxx-xxxxxxxxxxxx') | `string` | n/a | yes |
| vm\_domain\_name\_label | DNS name of the VM. The FQDN will be: <vm\_domain\_name\_label>.<location>.cloudapp.azure.com | `string` | n/a | yes |
| vm\_name | Name, hostname of the VM | `string` | n/a | yes |
| vm\_size | Size of the VM | `string` | `"Standard_D2s_v5"` | no |
| vm\_ubuntu\_server\_offer | Offer of the VM | `string` | `"0001-com-ubuntu-server-jammy"` | no |
| vm\_ubuntu\_server\_sku | SKU of the VM | `string` | `"22_04-lts-gen2"` | no |

## Outputs

| Name | Description |
|------|-------------|
| vm\_fqdn | n/a |
| vm\_id | n/a |
| vm\_public\_ip\_address | n/a |
| vm\_public\_key\_fingerprint\_sha256 | n/a |
| vm\_tls\_private\_key | n/a |
<!-- END_TF_DOCS -->
