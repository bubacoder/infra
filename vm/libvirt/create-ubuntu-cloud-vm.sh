#!/usr/bin/env bash
set -euo pipefail

# Creates a fully automated Ubuntu VM using cloud images and cloud-init via virt-install.
# Run with: sudo ./create-ubuntu-cloud-vm.sh
#
# Ubuntu cloud images: https://cloud-images.ubuntu.com/releases/

IMAGE_DIR="/var/lib/libvirt/images"
# shellcheck source=../lib-common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../lib-common.sh"

# === User configuration ===

# Network type: "nat" uses libvirt's default NAT network; "bridge" attaches directly
# to the LAN bridge (requires setup-bridge.sh to have been run first, bridge name below).
readonly NETWORK_TYPE="nat"  # "nat" | "bridge"
readonly BRIDGE_NAME="br0"

# renovate: datasource=endoflife depName=ubuntu
readonly UBUNTU_VERSION="26.04"

readonly USERNAME="buba"
# Password hash created with: docker run -it --rm alpine mkpasswd --method=SHA-512
# shellcheck disable=SC2016,SC2034  # SC2034: consumed by write_ubuntu_cloud_user_data() in lib-common.sh
readonly PASSWORD_HASH='$5$ZZvSaWFZz6GSdet7$spw97QIa9A1KmbWLHS0mqJuyUsRAfKJu4lWglYSaFK7'

readonly VMNAME="ubuntu-cloud-test"
readonly CPU_CORES=2
readonly MEMORY_SIZE=2048  # MB
readonly DISK_SIZE=100     # GB, thin-provisioned (qcow2 sparse)

# === Derived (do not edit) ===

readonly CLOUD_IMAGE="ubuntu-${UBUNTU_VERSION}-server-cloudimg-amd64.img"
# shellcheck disable=SC2034  # consumed by download_cloud_image() in lib-common.sh
readonly CLOUD_IMAGE_URL="https://cloud-images.ubuntu.com/releases/${UBUNTU_VERSION}/release/${CLOUD_IMAGE}"
# shellcheck disable=SC2034  # consumed by download_cloud_image() in lib-common.sh
readonly CHECKSUM_URL="https://cloud-images.ubuntu.com/releases/${UBUNTU_VERSION}/release/SHA256SUMS"
readonly CLOUD_INIT_DIR="/tmp/virt-cloud-init-${VMNAME}"

prepare_vm_disk() {
    local -r SRC_IMAGE="${IMAGE_DIR}/${CLOUD_IMAGE}"
    local -r VM_DISK="${IMAGE_DIR}/${VMNAME}.qcow2"

    if [ -e "${VM_DISK}" ]; then
        echo "VM disk already exists: ${VM_DISK}" >&2
        echo "Remove it first with: sudo rm -f ${VM_DISK}" >&2
        exit 1
    fi

    echo "Creating VM disk from cloud image..." >&2
    qemu-img convert -f qcow2 -O qcow2 "${SRC_IMAGE}" "${VM_DISK}"

    echo "Resizing disk to ${DISK_SIZE}G..." >&2
    qemu-img resize "${VM_DISK}" "${DISK_SIZE}G" >&2

    echo "${VM_DISK}"
}

create_cloud_init_config() {
    rm -rf "${CLOUD_INIT_DIR}"
    mkdir -p "${CLOUD_INIT_DIR}"

    local -r USER_DATA_FILE="${CLOUD_INIT_DIR}/user-data"
    local -r META_DATA_FILE="${CLOUD_INIT_DIR}/meta-data"

    write_ubuntu_cloud_user_data "${USER_DATA_FILE}"

    cat > "${META_DATA_FILE}" << EOF
instance-id: ${VMNAME}
local-hostname: ${VMNAME}
EOF

    echo "${CLOUD_INIT_DIR}"
}

create_vm() {
    local -r VM_DISK="$1"
    local -r INIT_DIR="$2"

    if virsh dominfo "${VMNAME}" &>/dev/null; then
        echo "VM '${VMNAME}' already exists. Remove it first with:" >&2
        echo "  virsh destroy ${VMNAME} && virsh undefine --remove-all-storage ${VMNAME}" >&2
        exit 1
    fi

    echo "Creating VM ${VMNAME}..."

    # Use the exact osinfo ID when available, otherwise fall back to detect
    local osinfo_arg="ubuntu${UBUNTU_VERSION}"
    if ! grep -qr "short-id>ubuntu${UBUNTU_VERSION}<" /usr/share/osinfo/os/ubuntu.com/ 2>/dev/null; then
        echo "Note: osinfo entry for ubuntu${UBUNTU_VERSION} not found, using detect=on,require=off" >&2
        osinfo_arg="detect=on,require=off"
    fi

    local network_arg
    if [[ "${NETWORK_TYPE}" == "bridge" ]]; then
        network_arg="bridge=${BRIDGE_NAME},model=virtio"
    else
        network_arg="network=default,model=virtio"
    fi

    virt-install \
        --name "${VMNAME}" \
        --memory "${MEMORY_SIZE}" \
        --vcpus "${CPU_CORES}" \
        --disk "path=${VM_DISK},format=qcow2,bus=virtio" \
        --import \
        --osinfo "${osinfo_arg}" \
        --network "${network_arg}" \
        --graphics none \
        --noautoconsole \
        --cloud-init "user-data=${INIT_DIR}/user-data,meta-data=${INIT_DIR}/meta-data,disable=on"

    echo ""
    echo "VM ${VMNAME} created and started successfully!"
    echo ""
    echo "Check VM status:"
    echo "  virsh list --all"
    echo ""
    echo "Wait for IP (DHCP may take ~30s):"
    echo "  virsh domifaddr ${VMNAME}"
    echo ""
    echo "Connect via SSH once cloud-init completes:"
    echo "  ssh ${USERNAME}@<vm-ip>"
    echo ""
    echo "Check cloud-init status on the VM:"
    echo "  ssh ${USERNAME}@<vm-ip> 'cloud-init status --wait'"
    echo ""
    echo "To remove the VM:"
    echo "  virsh destroy ${VMNAME} && virsh undefine --remove-all-storage ${VMNAME}"
}

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root (use sudo)" >&2
    exit 1
fi

for cmd in wget qemu-img virt-install virsh; do
    command -v "$cmd" >/dev/null || { echo "Missing required tool: $cmd" >&2; exit 1; }
done

parse_download_only_arg "$@"

download_cloud_image

if [ "$DOWNLOAD_ONLY" = true ]; then
    echo "--download-only flag provided. Exiting after downloading the image."
    exit 0
fi

VM_DISK=$(prepare_vm_disk)
trap 'rm -f "${VM_DISK}"' ERR
INIT_DIR=$(create_cloud_init_config)
create_vm "${VM_DISK}" "${INIT_DIR}"
