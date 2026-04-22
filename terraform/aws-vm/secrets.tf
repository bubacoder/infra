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

# NOTE: The secret value is intentionally NOT set here — storing credentials in
# Terraform state is a security risk. After apply, populate the secret out-of-band:
#   aws secretsmanager put-secret-value \
#     --secret-id "<vm_name>/git-credentials" \
#     --secret-string "https://<user>:<token>@github.com"
