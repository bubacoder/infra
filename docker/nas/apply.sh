#!/bin/bash

# shellcheck disable=SC1091
. ../common.sh

assert-hostname "NAS"
init

up infra portainer-agent
up infra node-exporter

up fileshare qbittorrent

up storage samba
up storage scrutiny-collector

cleanup
