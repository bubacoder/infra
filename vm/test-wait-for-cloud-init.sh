#!/usr/bin/env bash
set -euo pipefail

readonly TEST_DIR="$(mktemp -d)"
trap 'rm -rf "${TEST_DIR}"' EXIT

cat > "${TEST_DIR}/qm" <<'EOF'
#!/usr/bin/env bash
if [ "$2" = "cmd" ]; then
    [ "${TEST_WAIT_MODE:-}" != agent-failure ] || exit 1
    printf '%s\n' '{"result":[{"ip-addresses":[{"ip-address-type":"ipv4","ip-address":"192.0.2.10"}]}]}'
else
    [ "$5" = "${TEST_CLOUD_TIMEOUT:-1800}" ] || exit 42
    case "${TEST_WAIT_MODE:-}" in
        cloud-timeout) exit 1 ;;
        invalid) printf '%s\n' 'SENTINEL_PRIVATE invalid JSON' ;;
        incomplete) printf '%s\n' '{"pid":42}' ;;
        cloud-error) printf '%s\n' '{"exitcode":1,"out-data":"SENTINEL_PRIVATE error details"}' ;;
        *) printf '%s\n' '{"exitcode":0,"out-data":"status: done"}' ;;
    esac
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

# A full cloud-init budget remains even when the agent budget is just one second.
TEST_CLOUD_TIMEOUT=2400 PATH="${TEST_DIR}:${PATH}" bash "$(dirname "$0")/proxmox/wait-for-cloud-init.sh" 100 1 192.0.2.10 2400

for mode in agent-failure cloud-timeout invalid incomplete cloud-error; do
    if output=$(TEST_WAIT_MODE="${mode}" PATH="${TEST_DIR}:${PATH}" bash "$(dirname "$0")/proxmox/wait-for-cloud-init.sh" 100 1 192.0.2.10 2>&1); then
        echo "Expected wait failure for ${mode}" >&2
        exit 1
    fi
    case "${output}" in
        *SENTINEL_PRIVATE*) echo "Guest output leaked" >&2; exit 1 ;;
    esac
done

for invalid in 0 -1 86401 invalid; do
    if PATH="${TEST_DIR}:${PATH}" bash "$(dirname "$0")/proxmox/wait-for-cloud-init.sh" 100 "${invalid}" >/dev/null 2>&1 ||
        PATH="${TEST_DIR}:${PATH}" bash "$(dirname "$0")/proxmox/wait-for-cloud-init.sh" 100 1 '' "${invalid}" >/dev/null 2>&1; then
        echo "Accepted an invalid phase timeout" >&2
        exit 1
    fi
done
