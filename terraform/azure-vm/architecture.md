# Azure VM Infrastructure Architecture

## Overview

The `terraform/azure-vm` directory contains Terraform configurations for deploying a Virtual Machine in Azure with associated network setup and storage. This VM serves as a platform to test or host the Docker services from this repository. The infrastructure is designed to be easily deployable, secure, and maintainable.

## Architecture Components

The architecture consists of four main modules, each with specific responsibilities:

1. **Base Module (`modules/base`)**
   - Creates the foundational Azure resources
   - Defines the resource group 
   - Sets up the virtual network (10.0.0.0/16) and subnet (10.0.1.0/24)

2. **Storage Module (`modules/storage`)**
   - Provisions persistent storage for the VM
   - Creates a managed disk with configurable size (defaults to 10GB)
   - Implements lifecycle policies to prevent accidental destruction

3. **Key Vault Module (`modules/keyvault`)**
   - Secures sensitive credentials
   - Creates an Azure Key Vault with a randomized name
   - Stores Git credentials securely
   - Configures access policies for the current user

4. **VM Module (`modules/vm`)**
   - Deploys the virtual machine itself
   - Sets up networking (public IP, NIC, NSG)
   - Configures SSH access using generated keys
   - Attaches the data disk from the storage module
   - Implements cloud-init for first-boot configuration
   - Configures VM identity with Key Vault access

## Security Features

- **Network Security Groups**: Limited SSH and HTTPS access from specific IP addresses only
- **SSH Key Authentication**: Password authentication disabled
- **Azure Key Vault Integration**: Secure storage and retrieval of Git credentials
- **Managed Identity**: VM uses managed identity to access Key Vault, avoiding hardcoded credentials
- **TLS Requirements**: Storage accounts enforce TLS 1.2+ and HTTPS-only traffic
- **Limited Access**: NSG rules restrict access to admin source IP only

## Deployment Flow

1. Base infrastructure is created (resource group, network)
2. Storage and Key Vault are provisioned in parallel
3. The VM is deployed with references to the subnet, data disk, and Key Vault
4. Cloud-init scripts configure the system on first boot:
   - Upgrade packages
   - Install Git and Azure CLI
   - Retrieve Git credentials from Key Vault
   - Clone the repository
   - Set up data disk mount points
   - Bootstrap Ansible

## Cloud-Init Configuration

Cloud-init automates the VM's first-boot configuration through three components:

1. **cloud-init.yaml**: Main configuration for package installation and command execution
2. **repo-setup.sh**: Sets up Git credentials and clones the repository
3. **mount-storage.sh**: Handles data disk mounting and directory creation

The data disk is mounted at `/storage` with subdirectories created for:
- Torrent downloads and watch folders
- Media content (TV series, movies, audio)

## Task Management

The project uses [Taskfile](https://taskfile.dev/) (`Taskfile.azure-vm.yaml`) instead of Makefiles for task automation. Key tasks include:

- **plan**: Creates Terraform execution plan
- **apply**: Deploys the infrastructure and configures SSH keys
- **destroy/destroy-vm**: Removes resources (complete or VM-only)
- **connect-vm**: Establishes SSH connection to the VM
- **config-vm**: Runs Ansible configuration on the VM
- **start/stop/deallocate-vm**: Controls VM power state

## VM Specifications

- **Default Size**: Standard_D2s_v5
- **OS**: Ubuntu 24.04 LTS Server
- **Disk**: Premium_LRS OS disk + Standard_LRS data disk
- **Identity**: System-assigned managed identity
- **Network**: Public IP with DNS name label

## Data Persistence

The architecture maintains data persistence through:
- Managed data disk with `prevent_destroy` lifecycle policy
- Separate storage module for data isolation
- Automatic disk mounting on VM restart

## Security Best Practices

1. Git credentials are never stored in Terraform state; they are passed to Key Vault
2. SSH keys are generated during deployment and saved locally
3. VM access is restricted by IP address
4. Cloud-init scripts validate credentials before use
5. Only necessary permissions are granted to the VM's managed identity

## Conclusion

This architecture provides a secure, automated deployment of an Azure VM suitable for testing or hosting the Docker services defined in this repository. The modular design allows for easy customization and maintenance, while security considerations are implemented throughout the infrastructure.