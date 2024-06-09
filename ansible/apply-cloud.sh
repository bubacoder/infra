#!/bin/sh

cd $(dirname "$0")
ansible-playbook "playbooks/cloud.yaml" "$@"
