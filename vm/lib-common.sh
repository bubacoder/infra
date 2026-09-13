# shellcheck shell=bash
# Shared library for VM creation scripts.
# Sourced automatically by scripts via relative path — works both locally and after rsync to a remote host.

set -euo pipefail

readonly IMAGE_DIR="${IMAGE_DIR:-/var/lib/vz/template/iso}"
# shellcheck disable=SC2034  # used by scripts that source this file
readonly SNIPPETS_DIR="${SNIPPETS_DIR:-/var/lib/vz/snippets}"
# shellcheck disable=SC2034  # used by scripts that source this file
readonly VM_STORAGE="${VM_STORAGE:-local-lvm}"
# shellcheck disable=SC2034  # used by Proxmox VM creation scripts
readonly VM_BRIDGE="${VM_BRIDGE:-vmbr0}"

validate_vm_config() {
    local config_var
    for config_var in USERNAME VMNAME VMID CPU_CORES MAX_MEMORY_SIZE MIN_MEMORY_SIZE DISK_SIZE; do
        if [ -z "${!config_var:-}" ]; then
            echo "Missing required configuration value: ${config_var}" >&2
            exit 1
        fi
    done

    if ! [[ "${VMID}" =~ ^[0-9]+$ ]] || ! [[ "${CPU_CORES}" =~ ^[1-9][0-9]*$ ]] || \
        ! [[ "${MAX_MEMORY_SIZE}" =~ ^[1-9][0-9]*$ ]] || ! [[ "${MIN_MEMORY_SIZE}" =~ ^[1-9][0-9]*$ ]]; then
        echo "VMID, CPU_CORES, MAX_MEMORY_SIZE, and MIN_MEMORY_SIZE must be positive integers." >&2
        exit 1
    fi
}

get_authorized_keys_file() {
    local actual_user="${SUDO_USER:-${USER:-root}}"
    local actual_home
    actual_home=$(getent passwd "${actual_user}" | cut -d: -f6)
    printf '%s/.ssh/authorized_keys\n' "${actual_home}"
}

require_authorized_keys() {
    local authorized_keys_file
    authorized_keys_file=$(get_authorized_keys_file)

    if [ ! -s "${authorized_keys_file}" ] || ! ssh-keygen -l -f "${authorized_keys_file}" >/dev/null 2>&1; then
        echo "No usable SSH public key found in ${authorized_keys_file}." >&2
        echo "Add a public key before creating an SSH-key-only VM." >&2
        exit 1
    fi
}

get_authorized_keys() {
    sed 's/^/      - /' "$(get_authorized_keys_file)"
}

# Uses caller-defined: IMAGE_DIR, CLOUD_IMAGE, CLOUD_IMAGE_URL, CHECKSUM_URL
download_cloud_image() {
    local -r IMAGE_PATH="${IMAGE_DIR}/${CLOUD_IMAGE}"

    if [ -e "${IMAGE_PATH}" ]; then
        echo "Cloud image ${CLOUD_IMAGE} already downloaded"
    else
        echo "Downloading cloud image ${CLOUD_IMAGE}..."
        wget -q --show-progress -O "${IMAGE_PATH}" "${CLOUD_IMAGE_URL}"

        echo "Verifying SHA256 checksum..."
        local sha256sums_file
        sha256sums_file=$(mktemp)
        trap 'rm -f "${sha256sums_file}"' EXIT
        wget -q -O "${sha256sums_file}" "${CHECKSUM_URL}"

        cd "${IMAGE_DIR}"
        if ! sha256sum -c "${sha256sums_file}" --ignore-missing 2>/dev/null | grep -q "${CLOUD_IMAGE}: OK"; then
            echo "Checksum verification failed for ${CLOUD_IMAGE}" >&2
            rm -f "${IMAGE_PATH}"
            exit 1
        fi
        echo "Checksum verified successfully"
    fi
}

# Uses caller-defined: VMNAME, USERNAME
write_ubuntu_cloud_user_data() {
    local -r DEST_FILE="$1"
    # Reference: https://cloudinit.readthedocs.io/en/latest/reference/examples.html
    cat > "${DEST_FILE}" << EOF
#cloud-config
hostname: ${VMNAME}
fqdn: ${VMNAME}.local
manage_etc_hosts: true

users:
  - name: ${USERNAME}
    groups: sudo
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: true
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

final_message: "Cloud-init completed after \$UPTIME seconds"
EOF
}

check_vm_not_exists() {
    if qm status "${VMID}" &>/dev/null; then
        echo "VM ${VMID} already exists. Remove it first with:" >&2
        echo "  qm stop ${VMID} && qm destroy ${VMID}" >&2
        exit 1
    fi
}

parse_download_only_arg() {
    DOWNLOAD_ONLY=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --download-only)
                # shellcheck disable=SC2034  # read by scripts that source this file
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
}

report_vm_storage_preflight() {
    echo "Storage preflight for ${VM_STORAGE}:"
    pvesm status --storage "${VM_STORAGE}"

    if command -v lvs >/dev/null 2>&1; then
        echo "Thin pools (GiB):"
        lvs --noheadings --units g --nosuffix \
            --options vg_name,lv_name,lv_size,data_percent,metadata_percent \
            --select 'lv_attr=~^t'
    fi

    if command -v lvmconfig >/dev/null 2>&1; then
        local autoextend_threshold
        autoextend_threshold=$(lvmconfig --type full activation/thin_pool_autoextend_threshold | cut -d= -f2)
        echo "thin_pool_autoextend_threshold=${autoextend_threshold}"
        if [ "${autoextend_threshold}" -ge 100 ]; then
            echo "WARNING: thin pools cannot autoextend before they are full." >&2
        fi
    fi
}
