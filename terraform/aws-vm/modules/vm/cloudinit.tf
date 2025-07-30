data "cloudinit_config" "vm_config" {
  gzip          = true
  base64_encode = true

  part {
    content_type = "text/cloud-config"
    content = templatefile("${path.module}/cloud-init/cloud-init.yaml.tpl", {
      REPO_SETUP_SCRIPT = "/var/lib/cloud/instance/scripts/repo-setup.sh"
      REPO_DIR          = var.repo_directory
      ADMIN_USER        = var.admin_user
    })
  }

  part {
    content_type = "text/x-shellscript"
    filename     = "repo-setup.sh"
    content = templatefile("${path.module}/cloud-init/repo-setup.sh.tpl", {
      GIT_CREDENTIALS_SECRET_ID = var.git_credentials_secret_id
      REPO_URL                  = var.repo_url
      REPO_DIR                  = var.repo_directory
      REGION                    = var.region
    })
  }

  part {
    content_type = "text/x-shellscript-per-boot"
    filename     = "mount-storage.sh"
    content      = file("${path.module}/cloud-init/mount-storage.sh")
  }
}