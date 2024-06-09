#!/bin/sh

cd $(dirname "$0")
ansible-playbook "playbooks/mac-workstation.yaml" -v --ask-become-pass "$@"
