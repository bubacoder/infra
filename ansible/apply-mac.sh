#!/bin/sh

ansible-playbook -v playbooks/mac-base.yaml --ask-become-pass --limit local "$@"
