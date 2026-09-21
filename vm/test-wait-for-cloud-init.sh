#!/usr/bin/env bash
set -euo pipefail

readonly TEST_DIR="$(mktemp -d)"
trap 'rm -rf "${TEST_DIR}"' EXIT

cat > "${TEST_DIR}/qm" <<'EOF'
#!/usr/bin/env bash
if [ "$2" = "cmd" ]; then
    printf '%s\n' '{"result":[{"ip-addresses":[{"ip-address-type":"ipv4","ip-address":"192.0.2.10"}]}]}'
else
    printf '%s\n' '{"exitcode":0,"out-data":"status: done"}'
fi
EOF
chmod +x "${TEST_DIR}/qm"

output=$(PATH="${TEST_DIR}:${PATH}" bash "$(dirname "$0")/proxmox/wait-for-cloud-init.sh" 100 1 192.0.2.10)
case "${output}" in
    *"Guest agent ready; DHCP address: 192.0.2.10"*"status: done"*) ;;
    *)
        printf 'Expected cloud-init wait output, got: %s\n' "${output}" >&2
        exit 1
        ;;
esac
