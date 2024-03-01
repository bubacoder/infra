output "vm_id" {
  value = module.vm.virtual_machine_id
}

output "vm_public_ip_address" {
  value = module.vm.public_ip_address
}

output "vm_fqdn" {
  value = module.vm.fqdn
}

output "vm_tls_private_key" {
  value     = module.vm.tls_private_key
  sensitive = true
}

output "vm_public_key_fingerprint_sha256" {
  value = module.vm.public_key_fingerprint_sha256
}
