#!/usr/bin/env bash
# shellcheck disable=SC2034,SC2157,SC2269
set -euo pipefail

echo "Mounting storage..."

# EBS volume ID injected by Terraform at provisioning time
DATA_VOLUME_ID="${DATA_VOLUME_ID}"

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
    if [ -b "/dev/xvdf" ]; then
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

# Format with ext4 only if the volume has no existing filesystem (first boot only)
if ! blkid "$${DEVICE}" | grep -q "UUID="; then
    echo "Formatting $${DEVICE} as ext4..."
    mkfs.ext4 -F "$${DEVICE}"
fi

UUID=$(blkid -s UUID -o value "$${DEVICE}")
if [ -z "$${UUID}" ]; then
    echo "Error: Could not determine UUID for $${DEVICE}."
    exit 1
fi

mkdir -p /storage

# Persist the mount across reboots using stable UUID
if ! grep -q "UUID=$${UUID}" /etc/fstab; then
    echo "UUID=$${UUID} /storage ext4 defaults,nofail 0 2" >> /etc/fstab
fi

mount "UUID=$${UUID}" /storage

# Create standard directory structure
mkdir -p /storage/media/{movies,tvseries,audio}

echo "Storage mounted successfully at /storage"
