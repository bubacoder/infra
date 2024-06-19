#!/bin/sh

cd "$(dirname "$0")" || exit
ansible-playbook "playbooks/cloud.yaml" "$@"
