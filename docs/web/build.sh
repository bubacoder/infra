#!/bin/bash
set -euo pipefail

HUGO_PORT=1314
HUGO_BASEURL=http://localhost:${HUGO_PORT}
TAG=docs.example.com:latest

./update-docs.py

docker build -t ${TAG} --build-arg HUGO_BASEURL=${HUGO_BASEURL} .

# Configured in docker/stacks/tools/homelab-docs.yaml
# docker run -p ${HUGO_PORT}:80 ${TAG}
