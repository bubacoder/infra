#!/bin/bash

ANSIBLE_DIR=$(dirname "$0")

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
  # Installing Ansible on Ubuntu
  # https://docs.ansible.com/ansible/latest/installation_guide/installation_distros.html#installing-ansible-on-ubuntu

  apt-get update
  apt-get install --yes software-properties-common
  add-apt-repository --yes --update ppa:ansible/ansible
  apt-get install --yes ansible python3-pip

  pip install passlib ansible-lint
  ansible-galaxy install -r "${ANSIBLE_DIR}/requirements.yml"

elif [[ "$OSTYPE" == "darwin"* ]]; then
  # Mac OSX
  # Install Homebrew
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  # Install Ansible
  brew install ansible
  ansible-galaxy install -r "${ANSIBLE_DIR}/requirements.yml"

else
  echo "Platform not supported."
fi
