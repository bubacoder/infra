#!/bin/sh

# If passwordless sudo is not enabled on the hosts, need to execute with the "--ask-become-pass" parameter
# Dry-run with "--check --diff" or short: "-CD"

ansible-playbook ./nest.yaml --limit docker_hosts "$@"
