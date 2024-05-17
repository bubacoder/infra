#!/usr/bin/env bash

# Update Docker images with:
# UPDATE=true ./apply-local.sh

# Stop all containers:
# docker stop $(docker ps -a -q)

cd "hosts/$(hostname | tr '[:upper:]' '[:lower:]')" && ./apply.sh
