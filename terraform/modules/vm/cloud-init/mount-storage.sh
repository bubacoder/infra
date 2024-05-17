#!/usr/bin/env bash
set -euo pipefail

echo "Mounting storage..."

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
      ((counter++))
    fi
  done

  if [ "$success" -eq 0 ]; then
    echo "Error: $device is not available after $max_attempts attempts."
    exit 1
  else
    echo "$device is now available."
    create_dir "$mount_path"
    mount "$device" "$mount_path"
  fi
}

function create_dir() {
  local dir="$1"
  if [ ! -d "$dir" ]; then
    mkdir --parents "$dir"
  fi
}

mount_storage "/dev/sdc1" "/storage"

create_dir /storage/torrent-downloads
create_dir /storage/torrent-watch
create_dir /storage/media/tvseries
create_dir /storage/media/movies
create_dir /storage/media/audio
