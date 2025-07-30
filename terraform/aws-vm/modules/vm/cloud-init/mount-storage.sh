#!/bin/bash
set -e

DEVICE="/dev/nvme1n1"
MOUNT_POINT="/storage"

# Wait for device to be available
echo "Waiting for device $DEVICE to become available..."
timeout 60 bash -c "until [ -e $DEVICE ]; do sleep 1; done"

# Check if the device exists
if [ ! -e "$DEVICE" ]; then
    echo "Device $DEVICE not found!"
    exit 1
fi

# Check if the device is already formatted
if ! blkid $DEVICE &>/dev/null; then
    echo "Formatting $DEVICE with ext4..."
    mkfs.ext4 $DEVICE
fi

# Create mount point if it doesn't exist
if [ ! -d "$MOUNT_POINT" ]; then
    echo "Creating mount point $MOUNT_POINT..."
    mkdir -p $MOUNT_POINT
fi

# Check if it's already in fstab
if ! grep -q "$MOUNT_POINT" /etc/fstab; then
    echo "Adding to fstab..."
    echo "$DEVICE $MOUNT_POINT ext4 defaults,nofail 0 2" >> /etc/fstab
fi

# Mount the device
echo "Mounting $DEVICE to $MOUNT_POINT..."
mount $MOUNT_POINT || mount -a

# Create necessary directories
echo "Creating storage directories..."
mkdir -p $MOUNT_POINT/downloads/{complete,incomplete,torrent-files}
mkdir -p $MOUNT_POINT/media/{movies,tv,music}

echo "Storage setup completed successfully!"