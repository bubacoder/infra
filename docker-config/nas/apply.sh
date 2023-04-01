#!/bin/bash

. ../common.sh

up infra portainer-agent
up fileshare transmission
up storage samba
up storage scrutiny-collector
