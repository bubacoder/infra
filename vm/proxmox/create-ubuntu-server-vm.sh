#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
readonly CONFIG_FILE="${VM_CONFIG_FILE:-${SCRIPT_DIR}/ubuntu-server.env}"

if [ ! -r "${CONFIG_FILE}" ]; then
    echo "VM configuration not found: ${CONFIG_FILE}" >&2
    echo "Copy config-example/vm/proxmox/ubuntu-server.env to config/vm/proxmox/, edit it, and sync config/vm/ with vm/." >&2
    exit 1
fi

# shellcheck source=/dev/null
source "${CONFIG_FILE}"

# shellcheck source=../lib-common.sh
source "${SCRIPT_DIR}/../lib-common.sh"

validate_vm_config
: "${UBUNTU_VERSION:?Missing required configuration value: UBUNTU_VERSION}"
: "${AUTOINSTALL:?Missing required configuration value: AUTOINSTALL}"

# === Derived (do not edit) ===

readonly INSTALL_ISO="ubuntu-${UBUNTU_VERSION}-live-server-amd64.iso"
readonly CHECKSUM_URL="https://releases.ubuntu.com/${UBUNTU_VERSION}/SHA256SUMS"

get_authorized_keys_autoinstall() {
    echo "    authorized-keys:"
    sed 's/^/\      - "/; s/$/"/' "$(get_authorized_keys_file)"
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
    # SSH-key-only access; the installer locks this local password.
    password: "!"
    username: ${USERNAME}
  ssh:
    allow-pw: false
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
      --net0 "virtio,bridge=${VM_BRIDGE},firewall=0" \
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

if [ "$DOWNLOAD_ONLY" = false ] && [ "$AUTOINSTALL" = true ]; then
    require_authorized_keys
fi

download_installer

if [ "$DOWNLOAD_ONLY" = true ]; then
    echo "--download-only flag provided. Exiting after downloading the installer."
    exit 0
fi

create_vm

# Start the VM:
# qm start ${VMID}
