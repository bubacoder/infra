# Git credentials stored in AWS Secrets Manager.
# The EC2 instance retrieves these at boot via its IAM role (no login required).
resource "aws_secretsmanager_secret" "git_credentials" {
  name                    = "${var.vm_name}/git-credentials"
  description             = "Git credentials for cloning the infrastructure repository"
  recovery_window_in_days = 7

  tags = {
    Name = "${var.vm_name}-git-credentials"
  }
}

resource "aws_secretsmanager_secret_version" "git_credentials" {
  secret_id     = aws_secretsmanager_secret.git_credentials.id
  secret_string = var.git_credentials
}
