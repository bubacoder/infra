# shellcheck shell=bash
# Shared library for VM creation scripts.
# Sourced automatically by scripts via relative path — works both locally and after rsync to a remote host.

set -euo pipefail

IMAGE_DIR="${IMAGE_DIR:-/var/lib/vz/template/iso}"
# shellcheck disable=SC2034  # used by scripts that source this file
readonly SNIPPETS_DIR="/var/lib/vz/snippets"
# shellcheck disable=SC2034  # used by scripts that source this file
readonly VM_STORAGE="local-lvm"

get_authorized_keys() {
    local actual_user="${SUDO_USER:-${USER:-root}}"
    local actual_home
    actual_home=$(getent passwd "${actual_user}" | cut -d: -f6)
    local AUTHORIZED_KEYS_FILE="${actual_home}/.ssh/authorized_keys"
    if [ -s "$AUTHORIZED_KEYS_FILE" ]; then
        sed 's/^/      - /' "$AUTHORIZED_KEYS_FILE"
    fi
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

# Uses caller-defined: VMNAME, USERNAME, PASSWORD_HASH
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
