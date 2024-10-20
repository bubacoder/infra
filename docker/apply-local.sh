#!/usr/bin/env bash

# Update Docker images with:
# MODE=UPDATE ./apply-local.sh

# Stop all containers:
# docker stop $(docker ps -a -q)

CONFIG_DIR=../config/docker
cd "$(dirname "$0")" || exit
cd "${CONFIG_DIR}/$(hostname | tr '[:upper:]' '[:lower:]')" && ./apply.sh
