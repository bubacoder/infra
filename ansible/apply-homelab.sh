#!/bin/sh

ansible-playbook playbooks/homelab.yaml --limit "!local-debian,!azure-vm" "$@"
