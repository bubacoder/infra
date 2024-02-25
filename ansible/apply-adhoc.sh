#!/bin/bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Error: Invalid number of parameters provided."
  echo -e "Usage:\n  ./apply-adhoc.sh <hostname-in-inventory> <role-1>,<role-2> ..."
  echo -e "Example:\n  ./apply-adhoc.sh local-debian debian-base,debian-docker-host,debian-developer"
  exit 1
fi

create-playbook() {
  HOSTNAME=$1
  ROLES=$(echo "$2" | tr "," "\n")

  echo "
- name: Setup ${HOSTNAME}
  become: true
  hosts:
    - ${HOSTNAME}
  roles:"

  for ROLE in ${ROLES}
  do
    echo "    - role: ${ROLE}"
  done
}

PLAYBOOK=playbooks/adhoc.yaml

create-playbook "$1" "$2" > ${PLAYBOOK}
ansible-playbook ${PLAYBOOK}
