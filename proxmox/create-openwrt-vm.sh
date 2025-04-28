#!/usr/bin/env bash
set -euo pipefail

# OpenWRT version to install
# Check latest version at: https://downloads.openwrt.org/releases/
readonly OPENWRT_VERSION=24.10.1

# VM params
readonly VMNAME="openwrt"
readonly VMID=200
readonly CPU_CORES=1
readonly MEMORY_SIZE=256 # MB
readonly DISK_SIZE=512 # MB

# Flag to control download-only behavior
DOWNLOAD_ONLY=false

download_installer() {
    readonly IMAGE_PATH="openwrt-${OPENWRT_VERSION}.img.gz"
    readonly DOWNLOAD_URL="https://downloads.openwrt.org/releases/${OPENWRT_VERSION}/targets/x86/64/openwrt-${OPENWRT_VERSION}-x86-64-generic-ext4-combined.img.gz"

    if [ -e "${IMAGE_PATH}" ]; then
        echo "OpenWRT disk image ${IMAGE_PATH} already downloaded"
    else
        echo "Downloading OpenWRT disk image ${IMAGE_PATH}"
        wget -O "${IMAGE_PATH}" "${DOWNLOAD_URL}"
    fi
}

create_vm() {
    # extract disk image
    readonly VM_IMG="openwrt-${OPENWRT_VERSION}-vm-${VMID}.img"
    cp "openwrt-${OPENWRT_VERSION}.img.gz" "${VM_IMG}.gz"
    gunzip -f "./${VM_IMG}.gz" || true

    # resize the raw disk
    qemu-img resize -f raw "./${VM_IMG}" "${DISK_SIZE}M"

    # create VM. net0: LAN, net1: WAN
    qm create ${VMID} --name ${VMNAME} \
      --ostype l26 \
      --memory ${MEMORY_SIZE} \
      --cpu cputype=host --cores ${CPU_CORES} \
      --net0 virtio,bridge=vmbr0,firewall=0 \
      --net1 virtio,bridge=vmbr0,firewall=0 \
      --scsihw virtio-scsi-pci \
      --serial0 socket \
      --tablet 0

    # import the downloaded disk to the local-lvm storage, attaching it as a SCSI drive, set as boot disk
    qm set ${VMID} --scsi0 local-lvm:0,import-from="$(realpath ./${VM_IMG})",ssd=1
    qm set ${VMID} --boot order=scsi0

    # remove the imported disk image
    rm "${VM_IMG}"
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
