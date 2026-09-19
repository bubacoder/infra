# shellcheck shell=bash
set -euo pipefail

readonly TEST_DIR="$(mktemp -d)"
trap 'rm -rf "${TEST_DIR}"' EXIT

# shellcheck source=lib-common.sh
source "$(dirname "$0")/lib-common.sh"

export SSH_PUBLIC_KEY_FILE="${TEST_DIR}/bootstrap.pub"
touch "${SSH_PUBLIC_KEY_FILE}"
if [ "$(get_authorized_keys_file)" != "${SSH_PUBLIC_KEY_FILE}" ]; then
    echo "Configured SSH public key file was not selected" >&2
    exit 1
fi

get_authorized_keys() {
    printf '%s\n' '      - ssh-ed25519 test-key'
}

assert_contains() {
    case "$1" in
        *"$2"*) ;;
        *)
            printf 'Expected generated user data to contain: %s\n' "$2" >&2
            exit 1
            ;;
    esac
}

assert_not_contains() {
    case "$1" in
        *"$2"*)
            printf 'Expected generated user data not to contain: %s\n' "$2" >&2
            exit 1
            ;;
        *) ;;
    esac
}

export VMNAME="test"
export USERNAME="admin"
write_ubuntu_cloud_user_data "${TEST_DIR}/admin.yaml"
admin_data=$(<"${TEST_DIR}/admin.yaml")
assert_contains "${admin_data}" 'primary_group: admin'

export USERNAME="operator"
write_ubuntu_cloud_user_data "${TEST_DIR}/operator.yaml"
operator_data=$(<"${TEST_DIR}/operator.yaml")
assert_not_contains "${operator_data}" 'primary_group:'
