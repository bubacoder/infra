# Create security group
resource "aws_security_group" "vm" {
  name        = "${var.vm_name}-sg"
  description = "Security group for ${var.vm_name} VM"
  vpc_id      = data.aws_subnet.selected.vpc_id

  # SSH access from admin IP
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["${var.admin_source_address}/32"]
  }

  # HTTPS access from admin IP
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["${var.admin_source_address}/32"]
  }

  # Outbound internet access
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.vm_name}-sg"
  }
}

# Generate random ID for unique S3 bucket name
resource "random_id" "vm_bucket" {
  byte_length = 8
}

# Create S3 bucket for boot diagnostics
resource "aws_s3_bucket" "vm_logs" {
  bucket = "vm-logs-${random_id.vm_bucket.hex}"

  tags = {
    Name = "${var.vm_name}-logs"
  }
}

# Create an IAM role for the EC2 instance
resource "aws_iam_role" "vm_role" {
  name = "${var.vm_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

# Create an IAM instance profile
resource "aws_iam_instance_profile" "vm_profile" {
  name = "${var.vm_name}-profile"
  role = aws_iam_role.vm_role.name
}

# Create an IAM policy for accessing Secrets Manager
resource "aws_iam_policy" "secrets_access" {
  name        = "${var.vm_name}-secrets-access"
  description = "Allow access to specific secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Effect   = "Allow"
        Resource = var.secrets_manager_arn
      }
    ]
  })
}

# Attach the policy to the role
resource "aws_iam_role_policy_attachment" "secrets_access_attach" {
  role       = aws_iam_role.vm_role.name
  policy_arn = aws_iam_policy.secrets_access.arn
}

# Create an SSH key
resource "tls_private_key" "vm_ssh" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

# Create AWS key pair
resource "aws_key_pair" "vm_key" {
  key_name   = "${var.vm_name}-key"
  public_key = tls_private_key.vm_ssh.public_key_openssh
}

# Get subnet information
data "aws_subnet" "selected" {
  id = var.subnet_id
}

# Create EC2 instance
resource "aws_instance" "vm" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.vm_key.key_name
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.vm.id]
  iam_instance_profile   = aws_iam_instance_profile.vm_profile.name

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    delete_on_termination = true
    encrypted             = true
  }

  user_data = data.cloudinit_config.vm_config.rendered

  tags = {
    Name = var.vm_name
  }
}

# Create elastic IP and associate with instance
resource "aws_eip" "vm" {
  domain = "vpc"

  tags = {
    Name = "${var.vm_name}-eip"
  }
}

resource "aws_eip_association" "vm" {
  instance_id   = aws_instance.vm.id
  allocation_id = aws_eip.vm.id
}

# Attach EBS volume to EC2 instance
resource "aws_volume_attachment" "data_attachment" {
  device_name = "/dev/sdf"
  volume_id   = var.ebs_volume_id
  instance_id = aws_instance.vm.id
}