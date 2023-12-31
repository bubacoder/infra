#!/bin/bash

# shellcheck disable=SC1091
. ../../common.sh

assert-hostname "NAS"
init

up infra portainer-agent

up monitoring node-exporter

up fileshare qbittorrent

up storage samba
up storage scrutiny-collector

cleanup
