# Bootstrap selects an isolated state path with terraform init -backend-config.
# Standalone use retains Terraform's default terraform.tfstate path.
terraform {
  backend "local" {}
}

# To use a remote backend, replace the local block above after reviewing migration.
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
