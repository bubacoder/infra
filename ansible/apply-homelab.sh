#!/bin/sh

cd "$(dirname "$0")" || exit
ansible-playbook "playbooks/homelab.yaml" --limit "!local-debian,!azure-vm" "$@"
