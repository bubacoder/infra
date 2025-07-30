# Create an EBS volume for persistent storage
resource "aws_ebs_volume" "data" {
  availability_zone = "${var.region}a"
  size              = var.disk_size_gb
  type              = "gp3"

  tags = {
    Name = "${var.environment}-data-volume"
  }

  lifecycle {
    prevent_destroy = true
  }
}