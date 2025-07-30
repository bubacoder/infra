# Create AWS Secrets Manager for storing sensitive information
resource "aws_secretsmanager_secret" "main" {
  name                    = var.secrets_manager_name
  recovery_window_in_days = 0  # For easier testing - remove for production
}

# Store Git credentials in Secrets Manager
resource "aws_secretsmanager_secret_version" "git_credentials" {
  secret_id     = aws_secretsmanager_secret.main.id
  secret_string = jsonencode({
    "git-credentials" = var.git_credentials
  })
}