#!/bin/sh

set -eu

processed=false

for file in /workdir/*; do
  [ -f "$file" ] || continue

  filename=${file##*/}
  printf 'Processing %s ...\n' "$filename"
  envsubst < "$file" > "/processed/$filename"
  processed=true
done

if [ "$processed" = false ]; then
  printf '%s\n' 'No files processed' >&2
  exit 1
fi

ls /processed/
