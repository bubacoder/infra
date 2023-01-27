output "public_ip_address" {
  value = module.nest.public_ip_address
}

output "tls_private_key" {
  value     = module.nest.tls_private_key
  sensitive = true
}
