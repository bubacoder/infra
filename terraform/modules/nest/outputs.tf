output "public_ip_address" {
  value = azurerm_linux_virtual_machine.nest.public_ip_address
}

output "tls_private_key" {
  value     = tls_private_key.nest_ssh.private_key_pem
  sensitive = true
}

output "public_key_fingerprint_sha256" {
  value = tls_private_key.nest_ssh.public_key_fingerprint_sha256
}
