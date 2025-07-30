# AWS Virtual Machine Terraform Configuration

This directory contains Terraform configurations to deploy a virtual machine on AWS, along with the necessary network and security resources.

## Overview

The AWS VM architecture is designed to provide a secure, configurable environment for testing or running the Docker services defined in this repository. It includes persistent storage, secure credentials management, and automated setup via cloud-init.

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform installed (or OpenTofu as an alternative)
- Task runner installed (taskfile.dev)
- Git credentials for repository access

## Quick Start

1. Create configuration directory:
   ```bash
   mkdir -p ../../config/terraform/aws-vm
   ```

2. Create a variable file (../../config/terraform/aws-vm/infra.tfvars) with your settings:
   ```hcl
   vm_name = "yourname"
   vm_domain_name = "your-vm-name"
   region = "eu-west-1"
   ami_id = "ami-0123456789abcdef0"  # Ubuntu 24.04 LTS AMI for your region
   ```

3. Use Task commands to manage the infrastructure:
   ```bash
   # Initialize and validate
   task check
   
   # Create a plan
   task plan
   
   # Apply the plan
   task apply
   
   # Connect to the VM
   task connect-vm
   ```

## Architecture

For detailed architecture information, see [architecture.md](architecture.md).

## Variables

| Name | Description | Default |
|------|-------------|---------|
| region | AWS region | eu-west-1 |
| environment | Environment name | HomeInfra |
| storage_disk_size_gb | Size of the permanent disk in GB | 10 |
| vm_name | Name, hostname of the VM | - |
| vm_domain_name | DNS name of the VM | - |
| admin_user | Name of the administrative user on the VM | ec2-user |
| instance_type | EC2 instance type | t3.medium |
| ami_id | AMI ID for Ubuntu 24.04 LTS | - |
| admin_source_address | Allow connections (SSH, ...) only from this IP | - |
| git_credentials | Git credentials for repository access | - |
| repo_url | URL of the infrastructure repository | - |
| repo_directory | Name of the infrastructure repository directory | infra |