# Azure VM modules

The modules in the `terraform/azure-vm/modules` folder are implementing a Virtual Machine with the associated network setup and storage.
This VM can be used to test/host the Docker services of this repo.

**Usage:**

1. Login to Azure account (without browser access on device): `az login --use-device-code`
2. See the file `terraform/azure-vm/Taskfile.yaml` for available `task` commands for deploying/connection/deleting the VM.
3. Execute commands like `task plan` (in this folder) or `task azure-vm:plan` (anywhere within the repo).

Note: for the previous `Makefile` (which was replaced by `Taskfile`) see [MR #168](https://github.com/bubacoder/infra/pull/168).

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5 |
| azurerm | ~> 4.0 |
| random | ~> 3.0 |

## Providers

| Name | Version |
|------|---------|
| random | ~> 3.0 |

## Modules

| Name | Source | Version |
|------|--------|---------|
| base | ./modules/base | n/a |
| keyvault | ./modules/keyvault | n/a |
| storage | ./modules/storage | n/a |
| vm | ./modules/vm | n/a |

## Resources

| Name | Type |
|------|------|
| [random_string.keyvault_suffix](https://registry.terraform.io/providers/hashicorp/random/latest/docs/resources/string) | resource |

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
| vm\_ubuntu\_server\_offer | Offer of the VM | `string` | `"ubuntu-24_04-lts"` | no |
| vm\_ubuntu\_server\_sku | SKU of the VM | `string` | `"server"` | no |

## Outputs

| Name | Description |
|------|-------------|
| key\_vault\_name | The name of the Key Vault containing git credentials |
| vm\_fqdn | n/a |
| vm\_id | n/a |
| vm\_public\_ip\_address | n/a |
| vm\_public\_key\_fingerprint\_sha256 | n/a |
| vm\_tls\_private\_key | n/a |
<!-- END_TF_DOCS -->
