output "instance_id" {
  description = "EC2 instance ID"
  value       = module.ec2.id
}

output "public_ip" {
  description = "Public IP address of the instance"
  value       = var.allocate_elastic_ip ? aws_eip.main[0].public_ip : module.ec2.public_ip
}

output "ssh_private_key" {
  description = "SSH private key (ED25519) for connecting to the instance"
  value       = var.ssh_public_key == null ? tls_private_key.main[0].private_key_openssh : null
  sensitive   = true
}

output "public_key_fingerprint_sha256" {
  description = "SHA-256 fingerprint of the SSH public key"
  value       = var.ssh_public_key == null ? tls_private_key.main[0].public_key_fingerprint_sha256 : null
}

output "ami_id" {
  description = "AMI ID used for the instance"
  value       = var.ami_id != null ? var.ami_id : data.aws_ami.ubuntu[0].id
}

output "aws_region" {
  description = "AWS region where resources are deployed"
  value       = var.aws_region
}

output "secrets_manager_secret_name" {
  description = "Name of the Secrets Manager secret storing git credentials"
  value       = var.bootstrap_mode == "standalone" ? aws_secretsmanager_secret.git_credentials[0].name : null
}

output "data_volume_id" {
  description = "Persistent EBS data volume ID"
  value       = aws_ebs_volume.data.id
}

output "ssh_public_key" {
  description = "Public SSH key authorized for the administrator"
  value       = var.ssh_public_key != null ? local.ssh_public_key : tls_private_key.main[0].public_key_openssh
}

output "spot_instance" {
  description = "Whether a Spot instance is used"
  value       = var.spot_instance
}

output "spot_bid_status" {
  description = "Spot instance request bid status (null for on-demand)"
  value       = var.spot_instance ? module.ec2.spot_bid_status : null
}

output "spot_request_state" {
  description = "Spot instance request state (null for on-demand)"
  value       = var.spot_instance ? module.ec2.spot_request_state : null
}
