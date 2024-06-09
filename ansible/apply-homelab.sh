#!/bin/sh

cd $(dirname "$0")
ansible-playbook "playbooks/homelab.yaml" --limit "!local-debian,!azure-vm" "$@"
