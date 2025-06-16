#!/bin/bash
set -euo pipefail

# Source:
# - https://github.com/vrtmrz/obsidian-livesync/blob/main/docs/setup_own_server.md
# - https://raw.githubusercontent.com/vrtmrz/obsidian-livesync/main/utils/flyio/generate_setupuri.ts

# Change path if needed
. "${HOME}"/repos/infra/config/docker/.env
. "${HOME}"/repos/infra/config/docker/localhost/.env

COUCHDB_URL="https://couchdb.${MYDOMAIN}"
SCRIPT=generate-setupuri.ts

if [[ -z "$OBSIDIAN_LIVESYNC_DATABASE_NAME" ]]; then
    echo "ERROR: OBSIDIAN_LIVESYNC_DATABASE_NAME missing"
    exit 1
fi

if [[ -z "$OBSIDIAN_LIVESYNC_PASSPHRASE" ]]; then
    echo "ERROR: OBSIDIAN_LIVESYNC_PASSPHRASE missing"
    exit 1
fi

docker run --rm -it \
  -e hostname="${COUCHDB_URL}" \
  -e database="${OBSIDIAN_LIVESYNC_DATABASE_NAME}" \
  -e passphrase="${OBSIDIAN_LIVESYNC_PASSPHRASE}" \
  -e username="${COUCHDB_USER}" \
  -e password="${COUCHDB_PASSWORD}" \
  -v "$(pwd)/${SCRIPT}:/app/${SCRIPT}" \
  denoland/deno:latest run -A "/app/${SCRIPT}"
