#!/usr/bin/env bash
set -euo pipefail

# Deploy from adminhost: `ssh root@proxmox "bash -s" -- < create-ubuntu-server-vm.sh`

# Ubuntu version to install. The install media is downloaded automatically and attached to the VM.
# Check latest LTS version at: https://releases.ubuntu.com/
readonly UBUNTU_VERSION="24.04.2"
readonly INSTALL_ISO="ubuntu-${UBUNTU_VERSION}-live-server-amd64.iso"

# false: Manual installation is needed.
# true:  Edit the autoinstall config file below. Only need to approve the start of the installer on the VM console.
readonly AUTOINSTALL=true

# User settings for autoinstall
readonly USERNAME="buba"

# "initial_pswd" - created with `docker run -it --rm alpine mkpasswd --method=SHA-512`
# shellcheck disable=SC2016
readonly PASSWORD_HASH='$5$ZZvSaWFZz6GSdet7$spw97QIa9A1KmbWLHS0mqJuyUsRAfKJu4lWglYSaFK7'

# VM params
readonly VMNAME="nest2"
readonly VMID=150
readonly CPU_CORES=4
readonly MAX_MEMORY_SIZE=4096 # MB
readonly MIN_MEMORY_SIZE=1024 # MB (memory ballooning)
readonly DISK_SIZE=256 # GB (thin provisioned)

# Flag to control download-only behavior
DOWNLOAD_ONLY=false

get_authorized_keys_config() {
    AUTHORIZED_KEYS_FILE=~/.ssh/authorized_keys
    if [ -s "$AUTHORIZED_KEYS_FILE" ]; then
        echo "    authorized-keys:"
        sed 's/^/\      - "/; s/$/"/' "$AUTHORIZED_KEYS_FILE"
    fi
}

create_autoinstall_config() {
    readonly CONFIG_DIR=/var/lib/vz/snippets
    mkdir -p $CONFIG_DIR
    AUTOINSTALL_CONFIG_FILE=ubuntu-${UBUNTU_VERSION}-vendor.yaml

    # Config reference: https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html
    cat > ${CONFIG_DIR}/${AUTOINSTALL_CONFIG_FILE} << EOF
#cloud-config
autoinstall:
  version: 1
  locale: en_US.UTF-8
  refresh-installer:
    update: true
  keyboard:
    layout: us
  apt:
    geoip: true
  identity:
    hostname: ${VMNAME}
    password: ${PASSWORD_HASH}
    username: ${USERNAME}
  ssh:
    allow-pw: true
    install-server: true
$(get_authorized_keys_config)
  storage:
    layout:
      name: lvm
      match:
        size: largest
  packages:
    - qemu-guest-agent
  timezone: geoip
  updates: all
EOF
}

download_installer() {
    readonly INSTALL_ISO_PATH="/var/lib/vz/template/iso/${INSTALL_ISO}"
    if [ -e "${INSTALL_ISO_PATH}" ]; then
        echo "Installer ISO ${INSTALL_ISO} already downloaded"
    else
        echo "Downloading installer ISO ${INSTALL_ISO}"
        wget -O ${INSTALL_ISO_PATH} https://releases.ubuntu.com/${UBUNTU_VERSION}/${INSTALL_ISO}
    fi
}

create_vm() {
    qm create ${VMID} --name ${VMNAME} \
      --ostype l26 \
      --tags ubuntu \
      --memory ${MAX_MEMORY_SIZE} --balloon ${MIN_MEMORY_SIZE} \
      --cpu cputype=host --cores ${CPU_CORES} \
      --net0 virtio,bridge=vmbr0,firewall=0 \
      --agent enabled=1,freeze-fs-on-backup=1,type=virtio \
      --serial0 socket --tablet 0 \
      --scsihw virtio-scsi-single \
      --boot order="scsi0;ide2" --autostart 1 \
      --scsi0 local-lvm:${DISK_SIZE},ssd=1 \
      --ide2 local:iso/${INSTALL_ISO},media=cdrom

    if $AUTOINSTALL; then
        create_autoinstall_config
        qm set ${VMID} --ide0 local-lvm:cloudinit
        qm set ${VMID} --cicustom "vendor=local:snippets/${AUTOINSTALL_CONFIG_FILE}"
    fi

    echo "VM created successfully!"
}


# Parse command-line arguments
for arg in "$@"; do
    case $arg in
        --download-only)
            DOWNLOAD_ONLY=true
            shift
            ;;
        *)
            echo "Unknown argument: ${arg}"
            exit 1
            ;;
    esac
done


# Main logic
download_installer

if [ "$DOWNLOAD_ONLY" = true ]; then
    echo "--download-only flag provided. Exiting after downloading the installer."
    exit 0
fi

create_vm

# Start the VM
# qm start ${VMID}
