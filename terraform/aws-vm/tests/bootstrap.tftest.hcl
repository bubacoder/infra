# Offline plan tests. Mock AWS so this never creates or contacts cloud resources.
mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = { names = ["eu-central-1a"] }
  }
  mock_data "aws_ami" {
    defaults = { id = "ami-0123456789abcdef0" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws", dns_suffix = "amazonaws.com" }
  }
  mock_data "aws_region" {
    defaults = { name = "eu-central-1", region = "eu-central-1" }
  }
}

variables {
  admin_source_address = "8.8.8.8/32"
  repo_url             = "https://example.com/infra.git"
}

run "standalone_defaults" {
  command = plan
  assert {
    condition     = length(tls_private_key.main) == 1 && length(aws_secretsmanager_secret.git_credentials) == 1
    error_message = "Standalone mode must preserve generated SSH keys and Git credentials secret."
  }
  assert {
    condition     = length(aws_eip.main) == 0 && length(aws_iam_role_policy_attachment.ssm) == 0
    error_message = "Standalone mode must not allocate an EIP or change SSM access by default."
  }
}

run "external_bootstrap" {
  command = plan
  variables {
    bootstrap_mode      = "external"
    expected_account_id = "123456789012"
    ssh_public_key      = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest bootstrap@test"
    ami_id              = "ami-0123456789abcdef0"
    allocate_elastic_ip = true
  }
  assert {
    condition     = length(tls_private_key.main) == 0 && length(aws_secretsmanager_secret.git_credentials) == 0 && length(aws_iam_role_policy.secrets_access) == 0
    error_message = "External mode must not provision private keys or Git credentials."
  }
  assert {
    condition     = length(aws_eip.main) == 1 && length(aws_iam_role_policy_attachment.ssm) == 1
    error_message = "Bootstrap needs a stable IP and trusted SSM access."
  }
  assert {
    condition     = aws_volume_attachment.data.force_detach == false
    error_message = "External bootstrap must not forcibly detach persistent storage."
  }
  assert {
    condition     = length(data.aws_ami.ubuntu) == 0 && output.ami_id == "ami-0123456789abcdef0"
    error_message = "A pinned AMI must not drift to a newer image."
  }
}

run "unicode_ssh_key_comment" {
  command = plan
  variables {
    bootstrap_mode = "external"
    ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest opérateur@example"
    ami_id         = "ami-0123456789abcdef0"
  }
  assert {
    condition     = output.ssh_public_key == "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest"
    error_message = "EC2 key material must omit optional Unicode comments."
  }
}
