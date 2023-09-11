data "cloudinit_config" "nest_config" {
  gzip          = true
  base64_encode = true

  part {
    content_type = "text/cloud-config"
    content      = file("${path.module}/cloud-init/cloud-init.yaml")
  }

  part {
    content_type = "text/x-shellscript" # "text/x-shellscript-per-instance"
    content      = file("${path.module}/cloud-init/01-docker-setup.sh")
    filename     = "01-docker-setup.sh"
  }

  part {
    content_type = "text/x-shellscript" # "text/x-shellscript-per-boot"
    content      = file("${path.module}/cloud-init/02-docker-run.sh")
    filename     = "02-docker-run.sh"
  }

  part {
    content_type = "text/x-shellscript"
    content      = file("${path.module}/compose/homeassistant.yaml")
    filename     = "homeassistant.yaml"
  }

  part {
    content_type = "text/x-shellscript"
    content      = file("${path.module}/compose/jellyfin.yaml")
    filename     = "jellyfin.yaml"
  }

  part {
    content_type = "text/x-shellscript"
    content      = file("${path.module}/compose/plex.yaml")
    filename     = "plex.yaml"
  }

  part {
    content_type = "text/x-shellscript"
    content      = file("${path.module}/compose/portainer.yaml")
    filename     = "portainer.yaml"
  }

  part {
    content_type = "text/x-shellscript"
    content      = file("${path.module}/compose/syncthing.yaml")
    filename     = "syncthing.yaml"
  }

  part {
    content_type = "text/x-shellscript"
    content      = file("${path.module}/compose/transmission.yaml")
    filename     = "transmission.yaml"
  }

  part {
    content_type = "text/x-shellscript"
    content      = file("${path.module}/compose/unifi-controller.yaml")
    filename     = "unifi-controller.yaml"
  }

  part {
    content_type = "text/x-shellscript"
    content      = file("${path.module}/compose/filebrowser.yaml")
    filename     = "filebrowser.yaml"
  }
}
