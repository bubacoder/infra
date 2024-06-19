#!/usr/bin/env bash
set -e

cd "$(dirname "$0")" || exit
# shellcheck disable=SC1091
. ../../common.sh

assert_hostname "NAS"
init

set +e

up infra portainer-agent

up monitoring node-exporter
up monitoring scrutiny-collector

up fileshare qbittorrent

up storage samba

cleanup
