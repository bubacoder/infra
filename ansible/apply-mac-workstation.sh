#!/bin/sh

# Note: Execute this script locally on the target machine (uses `ansible_connection: local`)

cd "$(dirname "$0")" || exit
ansible-playbook "playbooks/mac-workstation.yaml" -v --ask-become-pass "$@"
