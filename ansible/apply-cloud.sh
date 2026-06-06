#!/bin/sh

cd "$(dirname "$0")" || exit
ansible-playbook "playbooks/cloud.yaml" \
  -i inventory/inventory.yaml \
  -i ../config/ansible/inventory/inventory.yaml \
  "$@"
