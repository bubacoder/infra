#!/usr/bin/env bash
set -euo pipefail

# This script creates a fully automated Ubuntu VM using cloud images and cloud-init.
# Unlike the autoinstall method, this requires zero manual interaction.

readonly SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
readonly CONFIG_FILE="${VM_CONFIG_FILE:-${SCRIPT_DIR}/ubuntu-cloud.env}"

if [ ! -r "${CONFIG_FILE}" ]; then
    echo "VM configuration not found: ${CONFIG_FILE}" >&2
    echo "Copy config-example/vm/proxmox/ubuntu-cloud.env to config/vm/proxmox/, edit it, and sync config/vm/ with vm/." >&2
    exit 1
fi

# shellcheck source=/dev/null
source "${CONFIG_FILE}"

# shellcheck source=../lib-common.sh
source "${SCRIPT_DIR}/../lib-common.sh"

validate_vm_config
: "${UBUNTU_VERSION:?Missing required configuration value: UBUNTU_VERSION}"

# === Derived (do not edit) ===

readonly CLOUD_IMAGE="ubuntu-${UBUNTU_VERSION}-server-cloudimg-amd64.img"
readonly CLOUD_USER_DATA_FILE="ubuntu-${UBUNTU_VERSION}-cloud-user.yaml"
readonly CLOUD_NETWORK_CONFIG_FILE="ubuntu-${UBUNTU_VERSION}-cloud-network.yaml"
# shellcheck disable=SC2034  # consumed by download_cloud_image() in lib-common.sh
readonly CLOUD_IMAGE_URL="https://cloud-images.ubuntu.com/releases/${UBUNTU_VERSION}/release/${CLOUD_IMAGE}"
# shellcheck disable=SC2034  # consumed by download_cloud_image() in lib-common.sh
readonly CHECKSUM_URL="https://cloud-images.ubuntu.com/releases/${UBUNTU_VERSION}/release/SHA256SUMS"

create_cloud_init_config() {
    mkdir -p "${SNIPPETS_DIR}"
    write_ubuntu_cloud_user_data "${SNIPPETS_DIR}/${CLOUD_USER_DATA_FILE}"

    # This VM creates one Ethernet NIC, so match it without relying on its OS-specific name.
    cat > "${SNIPPETS_DIR}/${CLOUD_NETWORK_CONFIG_FILE}" << EOF
version: 2
ethernets:
  primary:
    match:
      name: "*"
    dhcp4: true
EOF
}

create_vm() {
    local -r IMAGE_PATH="${IMAGE_DIR}/${CLOUD_IMAGE}"

    check_vm_not_exists

    echo "Creating VM ${VMNAME} (ID: ${VMID})..."

    # Create the VM without disk (we'll import it)
    qm create "${VMID}" --name "${VMNAME}" \
        --ostype l26 \
        --tags ubuntu,cloud-init \
        --memory "${MAX_MEMORY_SIZE}" --balloon "${MIN_MEMORY_SIZE}" \
        --cpu cputype=host --cores "${CPU_CORES}" \
        --net0 "virtio,bridge=${VM_BRIDGE},firewall=0" \
        --agent enabled=1,freeze-fs-on-backup=1,type=virtio \
        --serial0 socket --tablet 0 \
        --scsihw virtio-scsi-single \
        --boot order="scsi0" --autostart 1

    echo "Importing cloud image as VM disk..."
    qm importdisk "${VMID}" "${IMAGE_PATH}" "${VM_STORAGE}" --format raw

    # Attach the imported disk
    qm set "${VMID}" --scsi0 "${VM_STORAGE}:vm-${VMID}-disk-0,ssd=1"

    echo "Resizing disk to ${DISK_SIZE}..."
    qm resize "${VMID}" scsi0 "${DISK_SIZE}"

    echo "Configuring cloud-init..."
    qm set "${VMID}" --ide2 "${VM_STORAGE}:cloudinit"
    qm set "${VMID}" --cicustom "user=local:snippets/${CLOUD_USER_DATA_FILE},network=local:snippets/${CLOUD_NETWORK_CONFIG_FILE}"

    # Set cloud-init options that can be configured via qm
    qm set "${VMID}" --ciuser "${USERNAME}"

    echo "VM created successfully!"
    echo ""
    echo "To start the VM:"
    echo "  qm start ${VMID}"
    echo ""
    echo "To wait for guest readiness after boot:"
    echo "  bash ${SCRIPT_DIR}/wait-for-cloud-init.sh ${VMID}"
}

parse_download_only_arg "$@"

if [ "$DOWNLOAD_ONLY" = false ]; then
    require_authorized_keys
fi

download_cloud_image

if [ "$DOWNLOAD_ONLY" = true ]; then
    echo "--download-only flag provided. Exiting after downloading the image."
    exit 0
fi

report_vm_storage_preflight
create_cloud_init_config
create_vm
