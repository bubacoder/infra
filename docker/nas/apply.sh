#!/bin/bash

# Update Docker images with:
# PULL=true ./apply.sh

. ../common.sh

assert-hostname "NAS"
init

up infra portainer-agent
up infra node-exporter

up fileshare qbittorrent

up storage samba
up storage scrutiny-collector

cleanup
