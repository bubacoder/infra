output "ebs_volume_id" {
  value       = aws_ebs_volume.data.id
  description = "ID of the created EBS volume"
}