#!/usr/bin/env bash
set -euo pipefail

# Deploy from adminhost:
#   rsync -a vm/ root@proxmox:/tmp/vm/ && ssh root@proxmox bash /tmp/vm/proxmox/create-openwrt-vm.sh

# shellcheck source=../lib-common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib-common.sh"

# === User configuration ===

# Check latest version at: https://downloads.openwrt.org/releases/
# renovate: datasource=github-releases depName=openwrt/openwrt extractVersion=^v(?<version>.+)$
readonly OPENWRT_VERSION=25.12.4

readonly VMNAME="openwrt"
readonly VMID=200
readonly CPU_CORES=1
readonly MEMORY_SIZE=256 # MB
readonly DISK_SIZE=512 # MB

# === Derived (do not edit) ===

readonly CHECKSUM_URL="https://downloads.openwrt.org/releases/${OPENWRT_VERSION}/targets/x86/64/sha256sums"

download_installer() {
    local -r IMAGE_PATH="openwrt-${OPENWRT_VERSION}.img.gz"
    local -r DOWNLOAD_URL="https://downloads.openwrt.org/releases/${OPENWRT_VERSION}/targets/x86/64/openwrt-${OPENWRT_VERSION}-x86-64-generic-ext4-combined.img.gz"

    if [ -e "${IMAGE_PATH}" ]; then
        echo "OpenWRT disk image ${IMAGE_PATH} already downloaded"
    else
        echo "Downloading OpenWRT disk image ${IMAGE_PATH}"
        wget -q --show-progress -O "${IMAGE_PATH}" "${DOWNLOAD_URL}"
        echo "Verifying SHA256 checksum..."
        EXPECTED_SHA256="$(wget -qO- "${CHECKSUM_URL}" | awk '/generic-ext4-combined\.img\.gz$/ {print $1; exit}')"
        if [ -z "$EXPECTED_SHA256" ]; then
            echo "Failed to retrieve expected SHA256 from ${CHECKSUM_URL}" >&2
            exit 1
        fi
        echo "${EXPECTED_SHA256}  ${IMAGE_PATH}" | sha256sum -c -
    fi
}

create_vm() {
    check_vm_not_exists

    # extract disk image
    local -r VM_IMG="openwrt-${OPENWRT_VERSION}-vm-${VMID}.img"
    cp "openwrt-${OPENWRT_VERSION}.img.gz" "${VM_IMG}.gz"
    gunzip -f "./${VM_IMG}.gz" || true

    # resize the raw disk
    qemu-img resize -f raw "./${VM_IMG}" "${DISK_SIZE}M"

    # create VM. net0: LAN, net1: WAN
    qm create "${VMID}" --name "${VMNAME}" \
      --ostype l26 \
      --tags openwrt \
      --memory "${MEMORY_SIZE}" \
      --cpu cputype=host --cores "${CPU_CORES}" \
      --net0 virtio,bridge=vmbr0,firewall=0 \
      --net1 virtio,bridge=vmbr0,firewall=0 \
      --scsihw virtio-scsi-pci \
      --serial0 socket \
      --tablet 0

    # import the downloaded disk to the local-lvm storage, attaching it as a SCSI drive, set as boot disk
    qm set "${VMID}" --scsi0 local-lvm:0,import-from="$(realpath "./${VM_IMG}")",ssd=1
    qm set "${VMID}" --boot order=scsi0

    # remove the imported disk image
    rm "${VM_IMG}"
    echo "VM created successfully!"
}

parse_download_only_arg "$@"
download_installer

if [ "$DOWNLOAD_ONLY" = true ]; then
    echo "--download-only flag provided. Exiting after downloading the installer."
    exit 0
fi

create_vm

# Start the VM:
# qm start ${VMID}
