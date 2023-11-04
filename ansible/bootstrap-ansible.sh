#!/bin/sh

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
  # Installing Ansible on Ubuntu
  # https://docs.ansible.com/ansible/latest/installation_guide/installation_distros.html#installing-ansible-on-ubuntu

  apt update
  apt install --yes software-properties-common
  add-apt-repository --yes --update ppa:ansible/ansible
  apt install --yes ansible

  pip install passlib ansible-lint

elif [[ "$OSTYPE" == "darwin"* ]]; then
  # Mac OSX
  # Install Homebrew
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

  # Install Ansible
  brew install ansible

else
  echo "Platform not supported."
fi
