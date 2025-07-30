output "instance_id" {
  value       = aws_instance.vm.id
  description = "ID of the created EC2 instance"
}

output "public_ip" {
  value       = aws_eip.vm.public_ip
  description = "Public IP address of the EC2 instance"
}

output "public_dns" {
  value       = aws_eip.vm.public_dns
  description = "Public DNS name of the EC2 instance"
}

output "tls_private_key" {
  value       = tls_private_key.vm_ssh.private_key_pem
  description = "Private key for SSH access to the VM"
  sensitive   = true
}