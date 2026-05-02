#!/usr/bin/env bash
set -euo pipefail

echo "Mounting storage..."

function create_dir() {
  local dir="$1"
  if [ ! -d "$dir" ]; then
    mkdir --parents "$dir"
  fi
}

function mount_storage() {
  local device="$1"
  local mount_path="$2"
  local max_attempts=60
  local counter=0
  local success=0

  while [ "$success" -eq 0 ] && [ "$counter" -lt "$max_attempts" ]; do
    if [ -b "$device" ]; then
      success=1
    else
      sleep 1
      counter=$((counter + 1))
    fi
  done

  if ! [ -b "$device" ]; then
    echo "Error: $device is not available after $max_attempts attempts."
    exit 1
  fi

  echo "$device is now available."

  # Format with ext4 only if the volume has no existing filesystem (first boot only)
  if ! blkid "$device" | grep -q "UUID="; then
    echo "Formatting $device as ext4..."
    mkfs.ext4 -F "$device"
  fi

  local uuid
  uuid=$(blkid -s UUID -o value "$device")
  if [ -z "$uuid" ]; then
    echo "Error: Could not determine UUID for $device."
    exit 1
  fi

  create_dir "$mount_path"

  # Persist the mount across reboots using stable UUID
  if ! grep -q "UUID=$uuid" /etc/fstab; then
    echo "UUID=$uuid $mount_path ext4 defaults,nofail 0 2" >> /etc/fstab
  fi

  # Mount only if not already mounted (fstab may have handled it on reboot)
  if ! mountpoint -q "$mount_path"; then
    mount "UUID=$uuid" "$mount_path"
  fi
}

mount_storage "/dev/sdc1" "/storage"

create_dir /storage/torrent-downloads
create_dir /storage/torrent-watch
create_dir /storage/media/tvseries
create_dir /storage/media/movies
create_dir /storage/media/audio
