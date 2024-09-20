#!/usr/bin/env bash

# Update Docker images with:
# MODE=UPDATE ./apply-local.sh

# Stop all containers:
# docker stop $(docker ps -a -q)

cd "$(dirname "$0")" || exit
cd "hosts/$(hostname | tr '[:upper:]' '[:lower:]')" && ./apply.sh
