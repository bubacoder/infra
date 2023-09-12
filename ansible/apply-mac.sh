#!/bin/sh

ansible-playbook -v mac.yaml --ask-become-pass --limit mac "$@"
