#!/bin/sh

ansible-playbook playbooks/debian-base.yaml --limit minimal,docker_hosts "$@"
