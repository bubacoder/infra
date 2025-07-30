output "vm_public_ip" {
  value       = module.vm.public_ip
  description = "Public IP address of the AWS instance"
}

output "vm_fqdn" {
  value       = module.vm.public_dns
  description = "Public DNS name of the AWS instance"
}

output "vm_tls_private_key" {
  value       = module.vm.tls_private_key
  description = "Private key for SSH access to the VM"
  sensitive   = true
}

output "secrets_manager_name" {
  value       = module.secrets.secrets_manager_name
  description = "Name of the AWS Secrets Manager store"
}