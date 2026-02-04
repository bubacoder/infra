#!/usr/bin/env bash
set -euo pipefail

# Deploy from adminhost: `ssh root@proxmox "bash -s" -- < create-ubuntu-cloud-vm.sh`
#
# This script creates a fully automated Ubuntu VM using cloud images and cloud-init.
# Unlike the autoinstall method, this requires zero manual interaction.

# Ubuntu version to install. Cloud images are downloaded automatically.
# Check latest LTS version at: https://cloud-images.ubuntu.com/releases/
readonly UBUNTU_VERSION="24.04"
readonly CLOUD_IMAGE="ubuntu-${UBUNTU_VERSION}-server-cloudimg-amd64.img"
readonly CLOUD_IMAGE_URL="https://cloud-images.ubuntu.com/releases/${UBUNTU_VERSION}/release/${CLOUD_IMAGE}"

# User settings
readonly USERNAME="buba"

# Password hash created with: docker run -it --rm alpine mkpasswd --method=SHA-512
# shellcheck disable=SC2016
readonly PASSWORD_HASH='$5$ZZvSaWFZz6GSdet7$spw97QIa9A1KmbWLHS0mqJuyUsRAfKJu4lWglYSaFK7'

# VM params
readonly VMNAME="ubuntu-cloud-test"
readonly VMID=400
readonly CPU_CORES=4
readonly MAX_MEMORY_SIZE=4096 # MB
readonly MIN_MEMORY_SIZE=1024 # MB (memory ballooning)
readonly DISK_SIZE=256G       # Final disk size (thin provisioned)

# Storage locations
readonly IMAGE_DIR="/var/lib/vz/template/iso"
readonly SNIPPETS_DIR="/var/lib/vz/snippets"
readonly VM_STORAGE="local-lvm"

# Flag to control download-only behavior
DOWNLOAD_ONLY=false

get_authorized_keys() {
    local AUTHORIZED_KEYS_FILE=~/.ssh/authorized_keys
    if [ -s "$AUTHORIZED_KEYS_FILE" ]; then
        sed 's/^/      - /' "$AUTHORIZED_KEYS_FILE"
    fi
}

download_cloud_image() {
    local -r IMAGE_PATH="${IMAGE_DIR}/${CLOUD_IMAGE}"

    if [ -e "${IMAGE_PATH}" ]; then
        echo "Cloud image ${CLOUD_IMAGE} already downloaded"
    else
        echo "Downloading cloud image ${CLOUD_IMAGE}..."
        wget -q --show-progress -O "${IMAGE_PATH}" "${CLOUD_IMAGE_URL}"

        echo "Verifying SHA256 checksum..."
        local -r CHECKSUM_URL="https://cloud-images.ubuntu.com/releases/${UBUNTU_VERSION}/release/SHA256SUMS"
        wget -q -O /tmp/SHA256SUMS "${CHECKSUM_URL}"

        cd "${IMAGE_DIR}"
        if ! sha256sum -c /tmp/SHA256SUMS --ignore-missing 2>/dev/null | grep -q "${CLOUD_IMAGE}: OK"; then
            echo "Checksum verification failed for ${CLOUD_IMAGE}" >&2
            rm -f "${IMAGE_PATH}"
            exit 1
        fi
        echo "Checksum verified successfully"
    fi
}

create_cloud_init_config() {
    mkdir -p "${SNIPPETS_DIR}"
    local -r USER_DATA_FILE="ubuntu-${UBUNTU_VERSION}-cloud-user.yaml"

    # Cloud-init user-data format (different from autoinstall format)
    # Reference: https://cloudinit.readthedocs.io/en/latest/reference/examples.html
    cat > "${SNIPPETS_DIR}/${USER_DATA_FILE}" << EOF
#cloud-config
hostname: ${VMNAME}
fqdn: ${VMNAME}.local
manage_etc_hosts: true

users:
  - name: ${USERNAME}
    groups: sudo
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: false
    passwd: ${PASSWORD_HASH}
    ssh_authorized_keys:
$(get_authorized_keys)

packages:
  - qemu-guest-agent

package_update: true
package_upgrade: true

timezone: UTC

runcmd:
  - systemctl enable qemu-guest-agent
  - systemctl start qemu-guest-agent

# Signal cloud-init completion
final_message: "Cloud-init completed after \$UPTIME seconds"
EOF

    echo "${USER_DATA_FILE}"
}

create_vm() {
    local -r IMAGE_PATH="${IMAGE_DIR}/${CLOUD_IMAGE}"
    local -r USER_DATA_FILE="$1"

    echo "Creating VM ${VMNAME} (ID: ${VMID})..."

    # Create the VM without disk (we'll import it)
    qm create "${VMID}" --name "${VMNAME}" \
        --ostype l26 \
        --tags ubuntu,cloud-init \
        --memory "${MAX_MEMORY_SIZE}" --balloon "${MIN_MEMORY_SIZE}" \
        --cpu cputype=host --cores "${CPU_CORES}" \
        --net0 virtio,bridge=vmbr0,firewall=0 \
        --agent enabled=1,freeze-fs-on-backup=1,type=virtio \
        --serial0 socket --tablet 0 \
        --scsihw virtio-scsi-single \
        --boot order="scsi0" --autostart 1

    echo "Importing cloud image as VM disk..."
    qm importdisk "${VMID}" "${IMAGE_PATH}" "${VM_STORAGE}" --format qcow2

    # Attach the imported disk
    qm set "${VMID}" --scsi0 "${VM_STORAGE}:vm-${VMID}-disk-0,ssd=1"

    echo "Resizing disk to ${DISK_SIZE}..."
    qm resize "${VMID}" scsi0 "${DISK_SIZE}"

    echo "Configuring cloud-init..."
    qm set "${VMID}" --ide2 "${VM_STORAGE}:cloudinit"
    qm set "${VMID}" --cicustom "user=local:snippets/${USER_DATA_FILE}"

    # Set cloud-init options that can be configured via qm
    qm set "${VMID}" --ciuser "${USERNAME}"
    qm set "${VMID}" --ipconfig0 ip=dhcp

    echo "VM created successfully!"
    echo ""
    echo "To start the VM:"
    echo "  qm start ${VMID}"
    echo ""
    echo "To check cloud-init status after boot:"
    echo "  ssh ${USERNAME}@<vm-ip> 'cloud-init status --wait'"
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --download-only)
            DOWNLOAD_ONLY=true
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 [--download-only]"
            exit 1
            ;;
    esac
done

# Main logic
download_cloud_image

if [ "$DOWNLOAD_ONLY" = true ]; then
    echo "--download-only flag provided. Exiting after downloading the image."
    exit 0
fi

USER_DATA_FILE=$(create_cloud_init_config)
create_vm "${USER_DATA_FILE}"
