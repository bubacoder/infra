#!/usr/bin/env bash
set -euo pipefail

# Deploy from adminhost:
#   rsync -a vm/ root@proxmox:/tmp/vm/ && ssh root@proxmox bash /tmp/vm/proxmox/create-ubuntu-cloud-vm.sh
#
# This script creates a fully automated Ubuntu VM using cloud images and cloud-init.
# Unlike the autoinstall method, this requires zero manual interaction.

# shellcheck source=../lib-common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib-common.sh"

# === User configuration ===

# renovate: datasource=endoflife depName=ubuntu
readonly UBUNTU_VERSION="26.04"

readonly USERNAME="buba"
# Password hash created with: docker run -it --rm alpine mkpasswd --method=SHA-512
# shellcheck disable=SC2016,SC2034  # SC2034: consumed by write_ubuntu_cloud_user_data() in lib-common.sh
readonly PASSWORD_HASH='$5$ZZvSaWFZz6GSdet7$spw97QIa9A1KmbWLHS0mqJuyUsRAfKJu4lWglYSaFK7'

readonly VMNAME="ubuntu-cloud-test"
readonly VMID=400
readonly CPU_CORES=4
readonly MAX_MEMORY_SIZE=4096 # MB
readonly MIN_MEMORY_SIZE=1024 # MB (memory ballooning)
readonly DISK_SIZE=256G       # Final disk size (thin provisioned)

# === Derived (do not edit) ===

readonly CLOUD_IMAGE="ubuntu-${UBUNTU_VERSION}-server-cloudimg-amd64.img"
# shellcheck disable=SC2034  # consumed by download_cloud_image() in lib-common.sh
readonly CLOUD_IMAGE_URL="https://cloud-images.ubuntu.com/releases/${UBUNTU_VERSION}/release/${CLOUD_IMAGE}"
# shellcheck disable=SC2034  # consumed by download_cloud_image() in lib-common.sh
readonly CHECKSUM_URL="https://cloud-images.ubuntu.com/releases/${UBUNTU_VERSION}/release/SHA256SUMS"

create_cloud_init_config() {
    mkdir -p "${SNIPPETS_DIR}"
    local -r USER_DATA_FILE="ubuntu-${UBUNTU_VERSION}-cloud-user.yaml"
    write_ubuntu_cloud_user_data "${SNIPPETS_DIR}/${USER_DATA_FILE}"
    echo "${USER_DATA_FILE}"
}

create_vm() {
    local -r IMAGE_PATH="${IMAGE_DIR}/${CLOUD_IMAGE}"
    local -r USER_DATA_FILE="$1"

    check_vm_not_exists

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

parse_download_only_arg "$@"
download_cloud_image

if [ "$DOWNLOAD_ONLY" = true ]; then
    echo "--download-only flag provided. Exiting after downloading the image."
    exit 0
fi

USER_DATA_FILE=$(create_cloud_init_config)
create_vm "${USER_DATA_FILE}"
