# Azure VM modules

The modules in the `terraform/azure-vm/modules` folder are implementing a Virtual Machine with the associated network setup and storage.
This VM can be used to test/host the Docker services of this repo.

## Prerequisites

### Azure Storage Account for Remote State

Before using this Terraform configuration, create an Azure Storage Account to store the remote state.

**IMPORTANT**: The storage account name `tfstateinfrandomanimal` shown below is just an **example**. You must choose your own globally unique name.

#### Configuration Steps

1. **Choose a unique storage account name** (3-24 characters, lowercase letters and numbers only)
2. **Update the configuration files**:
   - `Taskfile.yaml`: Update the `STORAGE_ACCOUNT_NAME` variable
   - `backend.tf`: Update the `storage_account_name` value

3. **Create the storage account**:

```bash
# Login to Azure (if not already logged in)
az login --use-device-code

# Set your custom storage account name
STORAGE_ACCOUNT_NAME="your-unique-name-here"  # CUSTOMIZE THIS

# Create Storage Account for Terraform state (skip if already exists)
az storage account create \
  --name $STORAGE_ACCOUNT_NAME \
  --resource-group HomeInfra \
  --location westeurope \
  --sku Standard_LRS \
  --encryption-services blob \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false

# Create container for state files
az storage container create \
  --name azure-vm-state \
  --account-name $STORAGE_ACCOUNT_NAME \
  --auth-mode login

# Verify creation
az storage blob list \
  --account-name $STORAGE_ACCOUNT_NAME \
  --container-name azure-vm-state \
  --output table \
  --auth-mode login
```

4. **Assign RBAC permissions** (required for Azure AD authentication):

```bash
# Get your user object ID
CURRENT_USER=$(az ad signed-in-user show --query id -o tsv)

# Assign Storage Blob Data Contributor role
az role assignment create \
  --assignee "$CURRENT_USER" \
  --role "Storage Blob Data Contributor" \
  --scope "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/HomeInfra/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME"
```

### GitHub Actions OIDC Setup (Optional)

To enable automated Terraform plans on pull requests via GitHub Actions:

1. **Create Azure AD Application**:
```bash
# Set your repository details
export GITHUB_ORG="bubacoder"
export GITHUB_REPO="infra"
export SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Create application and service principal
APP_ID=$(az ad app create \
  --display-name "github-actions-terraform-azure-vm" \
  --query appId -o tsv)
echo "Application ID: ${APP_ID}"

az ad sp create --id ${APP_ID}

# Get Object ID for federated credentials
OBJECT_ID=$(az ad app show --id ${APP_ID} --query id -o tsv)
echo "Object ID: ${OBJECT_ID}"

# Assign Contributor role
az role assignment create \
  --assignee ${APP_ID} \
  --role Contributor \
  --scope /subscriptions/${SUBSCRIPTION_ID}
```

**Note:** After the Key Vault is created (on first `terraform apply`), you need to grant the service principal access to manage secrets:

```bash
# Get the Key Vault name from terraform output
KEYVAULT_NAME=$(cd terraform/azure-vm && terraform output -raw key_vault_name)

# Get the service principal object ID
SP_OBJECT_ID=$(az ad sp show --id ${APP_ID} --query id -o tsv)

# Add access policy for Terraform to manage secrets
az keyvault set-policy \
  --name ${KEYVAULT_NAME} \
  --object-id ${SP_OBJECT_ID} \
  --secret-permissions get list set delete
```

2. **Create Federated Credentials**:
```bash
# For pull requests
az ad app federated-credential create \
  --id ${OBJECT_ID} \
  --parameters '{
    "name": "github-pr",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'"${GITHUB_ORG}/${GITHUB_REPO}"':pull_request",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# For main branch (future use)
az ad app federated-credential create \
  --id ${OBJECT_ID} \
  --parameters '{
    "name": "github-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'"${GITHUB_ORG}/${GITHUB_REPO}"':ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# Verify credentials
az ad app federated-credential list --id ${OBJECT_ID}
```

3. **Configure GitHub Secrets** (Settings > Secrets and variables > Actions):
```bash
# Display values for GitHub secrets
echo "=== GitHub Secrets ==="
echo "AZURE_CLIENT_ID: ${APP_ID}"
echo "AZURE_TENANT_ID: $(az account show --query tenantId -o tsv)"
echo "AZURE_SUBSCRIPTION_ID: ${SUBSCRIPTION_ID}"
```

- Add `AZURE_CLIENT_ID`: Application ID from above
- Add `AZURE_TENANT_ID`: Tenant ID from above
- Add `AZURE_SUBSCRIPTION_ID`: Subscription ID from above

For more details, see the [Azure documentation](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure).

### State Migration

If migrating from local state to Azure remote state, use the migration task:

```bash
# From repository root
task azure-vm:migrate-state

# Or from this directory
task migrate-state
```

This will backup your local state and migrate it to Azure Blob Storage.

## Usage

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
