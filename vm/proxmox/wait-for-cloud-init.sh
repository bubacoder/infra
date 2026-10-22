#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <vmid> [agent-timeout-seconds] [expected-ipv4] [cloud-init-timeout-seconds]" >&2
}

if [ "$#" -lt 1 ] || [ "$#" -gt 4 ]; then
    usage
    exit 1
fi

readonly VMID="$1"
readonly TIMEOUT_SECONDS="${2:-600}"
readonly EXPECTED_IPV4="${3:-}"
readonly CLOUD_INIT_TIMEOUT_SECONDS="${4:-1800}"

if ! [[ "${VMID}" =~ ^[0-9]+$ ]] || ! [[ "${TIMEOUT_SECONDS}" =~ ^[1-9][0-9]{0,4}$ ]] ||
    ! [[ "${CLOUD_INIT_TIMEOUT_SECONDS}" =~ ^[1-9][0-9]{0,4}$ ]] ||
    [ "${TIMEOUT_SECONDS}" -gt 86400 ] || [ "${CLOUD_INIT_TIMEOUT_SECONDS}" -gt 86400 ]; then
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
            my $expected = shift;
            my $interfaces = decode_json(<STDIN>);
            $interfaces = $interfaces->{result} if ref $interfaces eq "HASH";
            die "Guest agent returned invalid network interfaces\n" unless ref $interfaces eq "ARRAY";
            for my $interface (@{$interfaces}) {
                for my $address (@{$interface->{"ip-addresses"} // []}) {
                    next unless $address->{"ip-address-type"} eq "ipv4";
                    next if $address->{"ip-address"} eq "127.0.0.1";
                    next if $expected ne q{} && $address->{"ip-address"} ne $expected;
                    print $address->{"ip-address"};
                    exit;
                }
            }
        ' "${EXPECTED_IPV4}" <<<"${interfaces}")
        if [ -n "${ipv4}" ]; then
            echo "Guest agent ready; DHCP address: ${ipv4}"
            break
        fi
    fi
    sleep 5
done

if [ -z "${ipv4:-}" ]; then
    echo "Timed out waiting ${TIMEOUT_SECONDS}s for guest agent and expected DHCP address on VM ${VMID}." >&2
    echo "This does not prove a boot failure: cloud-init may still be installing the agent. Inspect bootstrap:status; do not recreate an existing VM." >&2
    exit 1
fi

echo "Waiting up to ${CLOUD_INIT_TIMEOUT_SECONDS}s for cloud-init, including OS upgrades (separate from the agent wait)."
if ! result=$(qm guest exec "${VMID}" --timeout "${CLOUD_INIT_TIMEOUT_SECONDS}" -- cloud-init status --wait 2>/dev/null); then
    echo "Cloud-init wait failed or timed out on VM ${VMID}; preserve the VM and inspect bootstrap:status before resuming with bootstrap:vm-wait." >&2
    exit 1
fi
if ! exit_code=$(perl -MJSON::PP -0777 -e 'my $result = decode_json(<STDIN>); die unless ref $result eq "HASH" && defined $result->{exitcode}; print $result->{exitcode}' 2>/dev/null <<<"${result}"); then
    echo "Cloud-init response was invalid or incomplete on VM ${VMID}; preserve the guest and inspect bootstrap:status." >&2
    exit 1
fi
output=$(perl -MJSON::PP -0777 -e 'my $result = decode_json(<STDIN>); print $result->{"out-data"} // q{}' 2>/dev/null <<<"${result}")

# Never forward arbitrary guest output or cloud-init error details.
if [[ "${output}" =~ ^status:\ (done|running|error|disabled)$ ]]; then
    printf '%s\n' "${output}"
fi

if [ "${exit_code}" != "0" ]; then
    echo "cloud-init did not complete successfully on VM ${VMID}; inspect the guest privately. Do not configure or recreate it yet." >&2
    exit 1
fi
