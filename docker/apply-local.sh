#!/bin/bash

# Update Docker images with:
# PULL=true ./apply-local.sh

cd "$(hostname | tr '[:upper:]' '[:lower:]')" && ./apply.sh
