output "public_ip_address" {
  value = module.nest.public_ip_address
}

output "tls_private_key" {
  value     = module.nest.tls_private_key
  sensitive = true
}

output "public_key_fingerprint_sha256" {
  value = module.nest.public_key_fingerprint_sha256
}
