#!/bin/sh

ansible-playbook playbooks/mac-workstation.yaml -v --ask-become-pass "$@"
