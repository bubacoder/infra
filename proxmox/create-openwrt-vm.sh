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

# download and extract openwrt image
wget -O openwrt.img.gz https://downloads.openwrt.org/releases/${OPENWRT_VERSION}/targets/x86/64/openwrt-${OPENWRT_VERSION}-x86-64-generic-ext4-combined.img.gz
gunzip -f ./openwrt.img.gz || true

# resize the raw disk
qemu-img resize -f raw ./openwrt.img "${DISK_SIZE}M"

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
qm set ${VMID} --scsi0 local-lvm:0,import-from="$(realpath ./openwrt.img)",ssd=1
qm set ${VMID} --boot order=scsi0

echo "VM created successfully!"

# start the VM
# qm start ${VMID}
