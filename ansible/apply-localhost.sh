#!/bin/sh

cd "$(dirname "$0")" || exit
ansible-playbook "playbooks/homelab.yaml" --limit "$(hostname)" \
  -e ansible_connection=local \
  -e ansible_pipelining=false \
  "$@"
