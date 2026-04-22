# IAM role assumed by the EC2 instance
resource "aws_iam_role" "ec2" {
  name = "${var.vm_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.vm_name}-ec2-role"
  }
}

# Allow the EC2 instance to read the git credentials secret
resource "aws_iam_role_policy" "secrets_access" {
  name = "${var.vm_name}-secrets-access"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.git_credentials.arn
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.vm_name}-ec2-profile"
  role = aws_iam_role.ec2.name
}
