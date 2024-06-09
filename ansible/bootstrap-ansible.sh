#!/usr/bin/env bash
set -euo pipefail

readonly ANSIBLE_DIR=$(dirname "$0")

install_ansible_on_ubuntu() {
  # Installing Ansible on Ubuntu
  # https://docs.ansible.com/ansible/latest/installation_guide/installation_distros.html#installing-ansible-on-ubuntu
  apt-get update
  apt-get install --yes software-properties-common
  add-apt-repository --yes --update ppa:ansible/ansible
  apt-get install --yes ansible python3-pip

  pip install passlib ansible-lint
  ansible-galaxy install -r "${ANSIBLE_DIR}/requirements.yml"
}

install_ansible_on_macos() {
  # Install Homebrew
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Install Ansible
  brew install ansible
  ansible-galaxy install -r "${ANSIBLE_DIR}/requirements.yml"
}

case "$OSTYPE" in
  linux-gnu*)
    install_ansible_on_ubuntu
    ;;
  darwin*)
    install_ansible_on_macos
    ;;
  *)
    echo "Platform not supported: $OSTYPE"
    exit 1
    ;;
esac
