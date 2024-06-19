#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")" || exit

# Get the MYDOMAIN variable
# shellcheck disable=SC1091
. ../../docker/hosts/.env

HUGO_PORT=1314
HUGO_BASEURL=http://localhost:${HUGO_PORT}
TAG=docs.${MYDOMAIN}:latest

./update-docs.py

docker build -t ${TAG} --build-arg HUGO_BASEURL=${HUGO_BASEURL} .

# Configured in docker/stacks/tools/homelab-docs.yaml
# docker run -p ${HUGO_PORT}:80 ${TAG}
