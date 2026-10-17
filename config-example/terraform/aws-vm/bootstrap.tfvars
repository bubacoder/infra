# Public infrastructure inputs only. No Cloudflare/AdGuard tokens or passwords.
# bootstrap:init TARGET=aws fills the three exact account/CIDR/key placeholders.
# Review the detected values before planning; configured values are never refreshed.
bootstrap_mode       = "external"
expected_account_id  = "123456789012"
aws_region           = "eu-central-1"
vm_name              = "docker-aws"
admin_user           = "ubuntu"
architecture         = "x86_64"
instance_type        = "t3.small"
allocate_elastic_ip   = true
admin_source_address = "203.0.113.10/32" # Administrator's public IPv4 /32.
os_disk_size_gb       = 20
data_disk_size_gb     = 30
ssh_public_key       = "ssh-ed25519 REPLACE_WITH_YOUR_PUBLIC_KEY"
# Optional official Canonical AMI pin. Pin after reviewing the first plan to avoid
# silently selecting a newer image on future plans. Always apply a reviewed plan.
# ami_id = "ami-..."
