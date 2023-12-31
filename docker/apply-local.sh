#!/bin/bash

# Update Docker images with:
# UPDATE=true ./apply-local.sh

cd "hosts/$(hostname | tr '[:upper:]' '[:lower:]')" && ./apply.sh
