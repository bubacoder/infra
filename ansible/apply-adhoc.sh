#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Error: Invalid number of parameters provided."
  echo -e "Usage:\n  ./apply-adhoc.sh <hostname-in-inventory> <role-1>,<role-2> ..."
  echo -e "Example:\n  ./apply-adhoc.sh local-debian debian-base,debian-docker-host,debian-developer"
  exit 1
fi

create_playbook() {
  local hostname="$1"
  local roles=$(echo "$2" | tr "," "\n")

  echo "
- name: Setup ${hostname}
  become: true
  hosts:
    - ${hostname}
  roles:"

  for role in ${roles}; do
    echo "    - role: ${role}"
  done
}

cd $(dirname "$0")
readonly PLAYBOOK_FILE="playbooks/adhoc.yaml"
create_playbook "$1" "$2" > "${PLAYBOOK_FILE}"
ansible-playbook "${PLAYBOOK_FILE}"
