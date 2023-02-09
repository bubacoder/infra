#!/bin/bash

. ../common.sh


up infra portainer
up infra portainer_agent
up fileshare transmission
up storage samba
up storage scrutiny
