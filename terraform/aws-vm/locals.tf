locals {
  # EC2 ImportKeyPair accepts ASCII material only. Comments are optional and can
  # contain Unicode, so register only the OpenSSH key type and encoded key.
  ssh_public_key = var.ssh_public_key == null ? null : join(" ", slice(regexall("\\S+", var.ssh_public_key), 0, 2))

  # Maps architecture to AMI name pattern and default instance type
  arch_config = {
    x86_64 = {
      ami_pattern   = "ubuntu/images/hvm-ssd-gp3/${var.ubuntu_version}-amd64-server-*"
      instance_type = "t3.small"
    }
    arm64 = {
      ami_pattern   = "ubuntu/images/hvm-ssd-gp3/${var.ubuntu_version}-arm64-server-*"
      instance_type = "t4g.small"
    }
  }

  instance_type = coalesce(var.instance_type, local.arch_config[var.architecture].instance_type)

  # Normalise admin_source_address to CIDR notation
  admin_cidr = can(regex("/", var.admin_source_address)) ? var.admin_source_address : "${var.admin_source_address}/32"

  # Rendered cloud-init user data
  user_data = data.cloudinit_config.main.rendered
}
