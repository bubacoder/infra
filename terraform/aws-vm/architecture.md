# AWS VM Infrastructure Architecture

## Overview

The `terraform/aws-vm` directory contains Terraform configurations for deploying a Virtual Machine in AWS with associated network setup and storage. This VM serves as a platform to test or host the Docker services from this repository. The infrastructure is designed to be easily deployable, secure, and maintainable.

## Architecture Components

The architecture consists of four main modules, each with specific responsibilities:

1. **Base Module (`modules/base`)**
   - Creates the foundational AWS resources
   - Defines the VPC (10.0.0.0/16)
   - Sets up the subnet (10.0.1.0/24)
   - Configures internet gateway and routing tables

2. **Storage Module (`modules/storage`)**
   - Provisions persistent storage for the VM
   - Creates an EBS volume with configurable size (defaults to 10GB)
   - Implements lifecycle policies to prevent accidental destruction

3. **Secrets Module (`modules/secrets`)**
   - Secures sensitive credentials
   - Creates an AWS Secrets Manager with a randomized name
   - Stores Git credentials securely

4. **VM Module (`modules/vm`)**
   - Deploys the EC2 instance itself
   - Sets up networking (elastic IP, security groups)
   - Configures SSH access using generated keys
   - Attaches the EBS volume from the storage module
   - Implements cloud-init for first-boot configuration
   - Configures IAM role with Secrets Manager access

## Security Features

- **Security Groups**: Limited SSH and HTTPS access from specific IP addresses only
- **SSH Key Authentication**: Password authentication disabled
- **AWS Secrets Manager Integration**: Secure storage and retrieval of Git credentials
- **IAM Role**: VM uses IAM role to access Secrets Manager, avoiding hardcoded credentials
- **Encrypted Storage**: Root volume and EBS data volume are encrypted
- **Limited Access**: Security group rules restrict access to admin source IP only

## Deployment Flow

1. Base infrastructure is created (VPC, subnet, internet gateway)
2. Storage and Secrets Manager are provisioned in parallel
3. The VM is deployed with references to the subnet, EBS volume, and Secrets Manager
4. Cloud-init scripts configure the system on first boot:
   - Upgrade packages
   - Install Git and AWS CLI
   - Retrieve Git credentials from Secrets Manager
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

The project uses [Taskfile](https://taskfile.dev/) (`Taskfile.yaml`) instead of Makefiles for task automation. Key tasks include:

- **plan**: Creates Terraform execution plan
- **apply**: Deploys the infrastructure and configures SSH keys
- **destroy/destroy-vm**: Removes resources (complete or VM-only)
- **connect-vm**: Establishes SSH connection to the VM
- **config-vm**: Runs Ansible configuration on the VM
- **start/stop-vm**: Controls VM power state

## VM Specifications

- **Default Size**: t3.medium
- **OS**: Ubuntu 24.04 LTS Server
- **Disk**: gp3 root disk + gp3 data disk
- **Identity**: IAM role with limited permissions
- **Network**: Elastic IP with public DNS name

## Data Persistence

The architecture maintains data persistence through:
- EBS data volume with `prevent_destroy` lifecycle policy
- Separate storage module for data isolation
- Automatic disk mounting on VM restart

## Security Best Practices

1. Git credentials are never stored in Terraform state; they are passed to Secrets Manager
2. SSH keys are generated during deployment and saved locally
3. VM access is restricted by IP address
4. Cloud-init scripts validate credentials before use
5. Only necessary permissions are granted to the VM's IAM role

## Conclusion

This architecture provides a secure, automated deployment of an AWS VM suitable for testing or hosting the Docker services defined in this repository. The modular design allows for easy customization and maintenance, while security considerations are implemented throughout the infrastructure.