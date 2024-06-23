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

1. Loging to Azure account (without browser access on device): `az login --use-device-code`
2. See the file `terraform/Makefile` for available `make` commands for deploying/connection/deleting the VM.

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.5 |
| <a name="requirement_azurerm"></a> [azurerm](#requirement\_azurerm) | ~> 3.0 |

## Providers

No providers.

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_base"></a> [base](#module\_base) | ./modules/base | n/a |
| <a name="module_storage"></a> [storage](#module\_storage) | ./modules/storage | n/a |
| <a name="module_vm"></a> [vm](#module\_vm) | ./modules/vm | n/a |

## Resources

No resources.

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_admin_source_address"></a> [admin\_source\_address](#input\_admin\_source\_address) | Allow connections (SSH, ...) only from this IP | `string` | n/a | yes |
| <a name="input_admin_user"></a> [admin\_user](#input\_admin\_user) | Name of the adminustrative user on the VM | `string` | `"azureuser"` | no |
| <a name="input_git_credentials"></a> [git\_credentials](#input\_git\_credentials) | Git credentials for accessing the infrastructure repository. Will be written to ~/.git-credentials | `string` | n/a | yes |
| <a name="input_location"></a> [location](#input\_location) | Location of the resources | `string` | `"westeurope"` | no |
| <a name="input_repo_directory"></a> [repo\_directory](#input\_repo\_directory) | Name of the infrastructure repository directory | `string` | `"infra"` | no |
| <a name="input_repo_url"></a> [repo\_url](#input\_repo\_url) | URL of the infrastructure repository | `string` | n/a | yes |
| <a name="input_resourcegroup"></a> [resourcegroup](#input\_resourcegroup) | Name of Resource Group | `string` | `"HomeInfra"` | no |
| <a name="input_storage_disk_size_gb"></a> [storage\_disk\_size\_gb](#input\_storage\_disk\_size\_gb) | Size of the permanent disk in GB | `number` | `10` | no |
| <a name="input_vm_domain_name_label"></a> [vm\_domain\_name\_label](#input\_vm\_domain\_name\_label) | DNS name of the VM. The FQDN will be: <vm\_domain\_name\_label>.<location>.cloudapp.azure.com | `string` | n/a | yes |
| <a name="input_vm_name"></a> [vm\_name](#input\_vm\_name) | Name, hostname of the VM | `string` | n/a | yes |
| <a name="input_vm_size"></a> [vm\_size](#input\_vm\_size) | Size of the VM | `string` | `"Standard_D2s_v5"` | no |
| <a name="input_vm_ubuntu_server_offer"></a> [vm\_ubuntu\_server\_offer](#input\_vm\_ubuntu\_server\_offer) | Offer of the VM | `string` | `"0001-com-ubuntu-server-jammy"` | no |
| <a name="input_vm_ubuntu_server_sku"></a> [vm\_ubuntu\_server\_sku](#input\_vm\_ubuntu\_server\_sku) | SKU of the VM | `string` | `"22_04-lts-gen2"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_vm_fqdn"></a> [vm\_fqdn](#output\_vm\_fqdn) | n/a |
| <a name="output_vm_id"></a> [vm\_id](#output\_vm\_id) | n/a |
| <a name="output_vm_public_ip_address"></a> [vm\_public\_ip\_address](#output\_vm\_public\_ip\_address) | n/a |
| <a name="output_vm_public_key_fingerprint_sha256"></a> [vm\_public\_key\_fingerprint\_sha256](#output\_vm\_public\_key\_fingerprint\_sha256) | n/a |
| <a name="output_vm_tls_private_key"></a> [vm\_tls\_private\_key](#output\_vm\_tls\_private\_key) | n/a |
<!-- END_TF_DOCS -->
