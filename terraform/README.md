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

## Deployments

- `terraform/azure-vm` – [Full module docs](./azure-vm/README.md): A simple VM on Azure for testing infra deployment.
