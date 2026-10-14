#!/usr/bin/env bash
# shellcheck disable=SC2034,SC2157,SC2269
set -euo pipefail

echo "Mounting storage..."

# EBS volume ID injected by Terraform at provisioning time
DATA_VOLUME_ID="${DATA_VOLUME_ID}"
FORMAT_NEW_VOLUME="${FORMAT_NEW_VOLUME}"

# Locate the block device for the given EBS volume ID.
# On Nitro-based instances (t3, m5, t4g, etc.) EBS volumes appear as NVMe
# devices and are identified via /dev/disk/by-id/.
# On older (non-Nitro) instances they appear as /dev/xvdf.
find_device() {
    local vol_id="$1"
    local vol_id_nodash
    vol_id_nodash=$(echo "$${vol_id}" | tr -d '-')

    # NVMe path (Nitro instances) — more reliable than device name
    local nvme_link="/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_$${vol_id_nodash}"
    if [ -L "$${nvme_link}" ]; then
        realpath "$${nvme_link}"
        return 0
    fi

    # Fallback: legacy xvd device (non-Nitro instances)
    if [ -b "/dev/xvdf" ] && [ "$(lsblk -dn -o SERIAL /dev/xvdf | tr -d ' -')" = "$${vol_id_nodash}" ]; then
        echo "/dev/xvdf"
        return 0
    fi

    return 1
}

DEVICE=""
MAX_ATTEMPTS=60
for i in $(seq 1 "$${MAX_ATTEMPTS}"); do
    DEVICE=$(find_device "$${DATA_VOLUME_ID}" 2>/dev/null || true)
    if [ -n "$${DEVICE}" ]; then
        break
    fi
    sleep 1
done

if [ -z "$${DEVICE}" ]; then
    echo "Error: Data volume $${DATA_VOLUME_ID} not found after $${MAX_ATTEMPTS} seconds."
    exit 1
fi

echo "Found data volume at: $${DEVICE}"

# Refuse partitioned or unknown devices. Absence of a UUID alone is not blankness.
if [ "$(lsblk -nr -o NAME "$${DEVICE}" | wc -l)" -ne 1 ]; then
    echo "Error: refusing partitioned data device." >&2
    exit 1
fi
FSTYPE=$(blkid -s TYPE -o value "$${DEVICE}" || true)
# shellcheck disable=SC2193 # Terraform renders $${...} to bash variable expansion.
if [ -z "$${FSTYPE}" ]; then
    if [ -n "$(wipefs --no-act --noheadings --output TYPE "$${DEVICE}")" ]; then
        echo "Error: refusing data device with unknown signatures." >&2
        exit 1
    fi
    # External bootstrap authorizes first-time formatting from its private state,
    # not from byte contents. Fresh encrypted EBS devices need not read as zeroes.
    if [ "$${FORMAT_NEW_VOLUME}" != "true" ]; then
        if [ "$${1:-}" = "--defer-initialization" ]; then
            echo "Storage initialization deferred to the administrative host."
            exit 0
        fi
        echo "Error: storage initialization requires administrative-host approval." >&2
        exit 1
    fi
    echo "Formatting $${DEVICE} as ext4..."
    mkfs.ext4 "$${DEVICE}"
elif [ "$${FSTYPE}" != "ext4" ]; then
    echo "Error: refusing unsupported data filesystem." >&2
    exit 1
fi

UUID=$(blkid -s UUID -o value "$${DEVICE}")
if [ -z "$${UUID}" ]; then
    echo "Error: Could not determine UUID for $${DEVICE}."
    exit 1
fi

mkdir -p /storage

# Persist the mount across reboots using stable UUID
if awk '$2 == "/storage" {found=1} END {exit !found}' /etc/fstab; then
    if ! awk -v expected="UUID=$${UUID}" '$2 == "/storage" && $1 != expected {bad=1} END {exit bad}' /etc/fstab; then
        echo "Error: conflicting /storage entry in fstab." >&2
        exit 1
    fi
else
    echo "UUID=$${UUID} /storage ext4 defaults,nofail 0 2" >> /etc/fstab
fi

if mountpoint -q /storage; then
    test "$(findmnt -n -o UUID --target /storage)" = "$${UUID}"
else
    mount "UUID=$${UUID}" /storage
fi
test "$(findmnt -n -o UUID --target /storage)" = "$${UUID}"

# Create standard directory structure
mkdir -p /storage/media/{movies,tvseries,audio}

echo "Storage mounted successfully at /storage"
