#!/bin/sh

# If passwordless sudo is not enabled on the hosts, need to execute with the "--ask-become-pass" parameter

ansible-playbook ./nest.yaml "$@"
