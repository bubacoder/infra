+++
title = "Terraform"
weight = 4
+++

## Azure

Loging to Azure account (without browser access on device):
`az login --use-device-code`

## Makefile

See possible `make` commands in `Makefile`.

## Basic Terraform commands

Initialize the Terraform directory you changed into to download the required provider
`terraform init`

Ensure Terraform code is formatted properly:
`terraform fmt -recursive`

Ensure code has proper syntax and no errors:
`terraform validate`

See the execution plan and note the number of resources that will be created:
`terraform plan`

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >=1.2 |
| <a name="requirement_azurerm"></a> [azurerm](#requirement\_azurerm) | ~>3.0 |

## Providers

No providers.

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_base"></a> [base](#module\_base) | ./modules/base | n/a |
| <a name="module_nest"></a> [nest](#module\_nest) | ./modules/nest | n/a |
| <a name="module_storage"></a> [storage](#module\_storage) | ./modules/storage | n/a |

## Resources

No resources.

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_admin_source_address"></a> [admin\_source\_address](#input\_admin\_source\_address) | Allow admin access only from this IP | `string` | n/a | yes |
| <a name="input_location"></a> [location](#input\_location) | Location of the resources | `string` | `"westeurope"` | no |
| <a name="input_resourcegroup"></a> [resourcegroup](#input\_resourcegroup) | Name of Resource Group | `string` | `"HomeInfra"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_public_ip_address"></a> [public\_ip\_address](#output\_public\_ip\_address) | n/a |
| <a name="output_tls_private_key"></a> [tls\_private\_key](#output\_tls\_private\_key) | n/a |
<!-- END_TF_DOCS -->
