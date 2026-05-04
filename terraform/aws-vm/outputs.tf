output "instance_id" {
  description = "EC2 instance ID"
  value       = module.ec2.id
}

output "public_ip" {
  description = "Public IP address of the instance"
  value       = module.ec2.public_ip
}

output "ssh_private_key" {
  description = "SSH private key (ED25519) for connecting to the instance"
  value       = tls_private_key.main.private_key_openssh
  sensitive   = true
}

output "public_key_fingerprint_sha256" {
  description = "SHA-256 fingerprint of the SSH public key"
  value       = tls_private_key.main.public_key_fingerprint_sha256
}

output "ami_id" {
  description = "AMI ID used for the instance"
  value       = data.aws_ami.ubuntu.id
}

output "secrets_manager_secret_name" {
  description = "Name of the Secrets Manager secret storing git credentials"
  value       = aws_secretsmanager_secret.git_credentials.name
}
