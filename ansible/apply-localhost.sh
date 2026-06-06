#!/bin/sh

cd "$(dirname "$0")" || exit
ansible-playbook "playbooks/homelab.yaml" \
  -i inventory/inventory.yaml \
  -i ../config/ansible/inventory/inventory.yaml \
  -e ansible_connection=local \
  -e ansible_pipelining=false \
  --limit "$(hostname)" \
  "$@"
