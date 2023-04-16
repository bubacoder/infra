#!/bin/bash

. ../common.sh

up infra portainer-agent
up infra node-exporter

up fileshare qbittorrent

up storage samba
up storage scrutiny-collector
