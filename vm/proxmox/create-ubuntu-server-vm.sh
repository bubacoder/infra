#!/usr/bin/env bash
set -euo pipefail

# Deploy from adminhost:
#   rsync -a vm/ root@proxmox:/tmp/vm/ && ssh root@proxmox bash /tmp/vm/proxmox/create-ubuntu-server-vm.sh

# shellcheck source=../lib-common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib-common.sh"

# === User configuration ===

# Check https://releases.ubuntu.com/ for latest LTS point release; update manually.
readonly UBUNTU_VERSION="26.04"

# false: Manual installation is needed.
# true:  Edit the autoinstall config below. Only need to approve the start of the installer on the VM console.
readonly AUTOINSTALL=true

readonly USERNAME="buba"
# Password ("initial_pswd") hash created with: docker run -it --rm alpine mkpasswd --method=SHA-512
# shellcheck disable=SC2016
readonly PASSWORD_HASH='$5$ZZvSaWFZz6GSdet7$spw97QIa9A1KmbWLHS0mqJuyUsRAfKJu4lWglYSaFK7'

readonly VMNAME="ubuntu-server-test"
readonly VMID=300
readonly CPU_CORES=4
readonly MAX_MEMORY_SIZE=4096 # MB
readonly MIN_MEMORY_SIZE=1024 # MB (memory ballooning)
readonly DISK_SIZE=256 # GB (thin provisioned)

# === Derived (do not edit) ===

readonly INSTALL_ISO="ubuntu-${UBUNTU_VERSION}-live-server-amd64.iso"
readonly CHECKSUM_URL="https://releases.ubuntu.com/${UBUNTU_VERSION}/SHA256SUMS"

get_authorized_keys_autoinstall() {
    local actual_user="${SUDO_USER:-${USER:-root}}"
    local actual_home
    actual_home=$(getent passwd "${actual_user}" | cut -d: -f6)
    local AUTHORIZED_KEYS_FILE="${actual_home}/.ssh/authorized_keys"
    if [ -s "$AUTHORIZED_KEYS_FILE" ]; then
        echo "    authorized-keys:"
        sed 's/^/\      - "/; s/$/"/' "$AUTHORIZED_KEYS_FILE"
    fi
}

create_autoinstall_config() {
    mkdir -p "${SNIPPETS_DIR}"
    AUTOINSTALL_CONFIG_FILE=ubuntu-${UBUNTU_VERSION}-vendor.yaml

    # Config reference: https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html
    cat > "${SNIPPETS_DIR}/${AUTOINSTALL_CONFIG_FILE}" << EOF
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
$(get_authorized_keys_autoinstall)
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
    local -r INSTALL_ISO_PATH="${IMAGE_DIR}/${INSTALL_ISO}"
    if [ -e "${INSTALL_ISO_PATH}" ]; then
        echo "Installer ISO ${INSTALL_ISO} already downloaded"
    else
        cd "${IMAGE_DIR}"
        echo "Downloading installer ISO ${INSTALL_ISO}"
        local -r ISO_URL="https://releases.ubuntu.com/${UBUNTU_VERSION}/${INSTALL_ISO}"
        wget -q --show-progress -O "${INSTALL_ISO_PATH}" "${ISO_URL}"
        echo "Verifying SHA256 checksum..."
        local sha256sums_file
        sha256sums_file=$(mktemp)
        trap 'rm -f "${sha256sums_file}"' EXIT
        wget -q -O "${sha256sums_file}" "${CHECKSUM_URL}"
        if ! sha256sum -c "${sha256sums_file}" --ignore-missing | grep -q "${INSTALL_ISO}: OK"; then
            echo "Checksum verification failed for ${INSTALL_ISO}" >&2
            exit 1
        fi
        # Optional: also verify GPG signature with SHA256SUMS.gpg and Ubuntu keys
    fi
}

create_vm() {
    check_vm_not_exists

    qm create "${VMID}" --name "${VMNAME}" \
      --ostype l26 \
      --tags ubuntu \
      --memory "${MAX_MEMORY_SIZE}" --balloon "${MIN_MEMORY_SIZE}" \
      --cpu cputype=host --cores "${CPU_CORES}" \
      --net0 virtio,bridge=vmbr0,firewall=0 \
      --agent enabled=1,freeze-fs-on-backup=1,type=virtio \
      --serial0 socket --tablet 0 \
      --scsihw virtio-scsi-single \
      --boot order="scsi0;ide2" --autostart 1 \
      --scsi0 "${VM_STORAGE}:${DISK_SIZE},ssd=1" \
      --ide2 "local:iso/${INSTALL_ISO},media=cdrom"

    if [ "$AUTOINSTALL" = true ]; then
        create_autoinstall_config
        qm set "${VMID}" --ide0 "${VM_STORAGE}:cloudinit"
        qm set "${VMID}" --cicustom "vendor=local:snippets/${AUTOINSTALL_CONFIG_FILE}"
    fi

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
