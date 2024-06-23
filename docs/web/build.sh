#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")" || exit

# Get the MYDOMAIN variable
# shellcheck disable=SC1091
. ../../docker/hosts/.env

SITE_DOMAIN=docs.${MYDOMAIN}
HUGO_BASEURL=https://${SITE_DOMAIN}
TAG=${SITE_DOMAIN}:latest

# Add parameter for verbose output: --verbose
./update-docs.py

# Add parameters for debugging: --progress=plain --no-cache
docker build -t "${TAG}" --build-arg HUGO_BASEURL="${HUGO_BASEURL}" .

# Configured in docker/stacks/tools/homelab-docs.yaml
# docker run -p 1314:80 ${TAG}
