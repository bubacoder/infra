# Remote state backend using S3 + DynamoDB locking.
# Uncomment after creating the S3 bucket and DynamoDB table.
# See README.md for setup instructions.
#
# terraform {
#   backend "s3" {
#     bucket         = "CUSTOMIZE-terraform-state-aws-vm"
#     key            = "aws-vm/terraform.tfstate"
#     region         = "eu-central-1"
#     encrypt        = true
#     dynamodb_table = "terraform-locks"
#   }
# }
