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
  count = var.bootstrap_mode == "standalone" ? 1 : 0
  name  = "${var.vm_name}-secrets-access"
  role  = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.git_credentials[0].arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  count      = var.bootstrap_mode == "external" ? 1 : 0
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

moved {
  from = aws_iam_role_policy.secrets_access
  to   = aws_iam_role_policy.secrets_access[0]
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.vm_name}-ec2-profile"
  role = aws_iam_role.ec2.name
}
