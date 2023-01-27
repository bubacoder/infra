output "public_ip_address" {
  value = azurerm_linux_virtual_machine.nest.public_ip_address
}

output "tls_private_key" {
  value     = tls_private_key.nest_ssh.private_key_pem
  sensitive = true
}
