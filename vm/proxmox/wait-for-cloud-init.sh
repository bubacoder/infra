#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <vmid> [timeout-seconds]" >&2
}

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    usage
    exit 1
fi

readonly VMID="$1"
readonly TIMEOUT_SECONDS="${2:-600}"

if ! [[ "${VMID}" =~ ^[0-9]+$ ]] || ! [[ "${TIMEOUT_SECONDS}" =~ ^[1-9][0-9]*$ ]]; then
    usage
    exit 1
fi

readonly DEADLINE=$((SECONDS + 10#${TIMEOUT_SECONDS}))

command -v perl >/dev/null 2>&1 || {
    echo "Perl is required to read the guest agent response." >&2
    exit 1
}

while [ "${SECONDS}" -lt "${DEADLINE}" ]; do
    if interfaces=$(qm guest cmd "${VMID}" network-get-interfaces 2>/dev/null); then
        ipv4=$(perl -MJSON::PP -0777 -e '
            my $interfaces = decode_json(<STDIN>);
            for my $interface (@{$interfaces}) {
                for my $address (@{$interface->{"ip-addresses"} // []}) {
                    next unless $address->{"ip-address-type"} eq "ipv4";
                    next if $address->{"ip-address"} eq "127.0.0.1";
                    print $address->{"ip-address"};
                    exit;
                }
            }
        ' <<<"${interfaces}")
        if [ -n "${ipv4}" ]; then
            echo "Guest agent ready; DHCP address: ${ipv4}"
            break
        fi
    fi
    sleep 5
done

if [ -z "${ipv4:-}" ]; then
    echo "Timed out waiting ${TIMEOUT_SECONDS}s for guest agent and DHCP address on VM ${VMID}." >&2
    exit 1
fi

remaining_seconds=$((DEADLINE - SECONDS))
if [ "${remaining_seconds}" -le 0 ]; then
    echo "Timed out before cloud-init could be checked on VM ${VMID}." >&2
    exit 1
fi

result=$(qm guest exec "${VMID}" --timeout "${remaining_seconds}" -- cloud-init status --wait)
exit_code=$(perl -MJSON::PP -0777 -e 'my $result = decode_json(<STDIN>); print $result->{exitcode} // q{}' <<<"${result}")
output=$(perl -MJSON::PP -0777 -e 'my $result = decode_json(<STDIN>); print $result->{"out-data"} // q{}' <<<"${result}")

if [ -n "${output}" ]; then
    printf '%s\n' "${output}"
fi

if [ "${exit_code}" != "0" ]; then
    echo "cloud-init did not complete successfully on VM ${VMID}." >&2
    exit 1
fi
