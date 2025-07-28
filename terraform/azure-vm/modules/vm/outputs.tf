output "virtual_machine_id" {
  value = azurerm_linux_virtual_machine.vm.virtual_machine_id
}

output "public_ip_address" {
  value = azurerm_linux_virtual_machine.vm.public_ip_address
}

output "fqdn" {
  value = azurerm_public_ip.vm.fqdn
}

output "tls_private_key" {
  value     = tls_private_key.vm_ssh.private_key_pem
  sensitive = true
}

output "public_key_fingerprint_sha256" {
  value = tls_private_key.vm_ssh.public_key_fingerprint_sha256
}

output "identity_principal_id" {
  value       = azurerm_linux_virtual_machine.vm.identity[0].principal_id
  description = "Principal ID of the VM's managed identity"
}
