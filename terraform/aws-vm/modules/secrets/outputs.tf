output "secrets_manager_name" {
  value       = aws_secretsmanager_secret.main.name
  description = "Name of the AWS Secrets Manager"
}

output "secrets_manager_arn" {
  value       = aws_secretsmanager_secret.main.arn
  description = "ARN of the AWS Secrets Manager"
}

output "git_credentials_secret_id" {
  value       = aws_secretsmanager_secret.main.id
  description = "Secret ID for Git credentials"
}