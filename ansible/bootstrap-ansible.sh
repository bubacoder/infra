#!/usr/bin/env bash
set -euo pipefail

readonly ANSIBLE_DIR=$(dirname "$0")

get_debian_version() {
  if [ -f /etc/debian_version ]; then
    cat /etc/debian_version
  else
    echo "Debian version file not found!"
    exit 1
  fi
}

install_ansible_on_ubuntu() {
  # Installing Ansible on Ubuntu
  # https://docs.ansible.com/ansible/latest/installation_guide/installation_distros.html#installing-ansible-on-ubuntu
  apt-get update
  apt-get install --yes software-properties-common
  add-apt-repository --yes --update ppa:ansible/ansible
  apt-get install --yes --no-install-recommends ansible python3-pip

  # "--ignore-installed" is added to fix error "Cannot uninstall PyYAML 6.0.1 ... The package was installed by debian."
  pip install passlib ansible-lint --ignore-installed --break-system-packages
  ansible-galaxy install -r "${ANSIBLE_DIR}/requirements.yml"
}

install_ansible_on_debian() {
  # Installing Ansible on Debian
  # https://docs.ansible.com/ansible/latest/installation_guide/installation_distros.html#installing-ansible-on-debian
  # "While Ansible is available from the main Debian repository, it can be out of date. To get a more recent version, Debian users can use the Ubuntu PPA."
  apt-get update
  apt-get install --yes wget pgp

  readonly DEBIAN_VERSION=$(get_debian_version)

  # Determine the Ubuntu codename based on Debian version
  case "$DEBIAN_VERSION" in
    trixie*|13*)
      UBUNTU_CODENAME="noble"
      ;;
    12*)
      UBUNTU_CODENAME="jammy"
      ;;
    11*)
      UBUNTU_CODENAME="focal"
      ;;
    10*)
      UBUNTU_CODENAME="bionic"
      ;;
    *)
      echo "Unsupported Debian version: $DEBIAN_VERSION"
      exit 1
      ;;
  esac

  wget -O- "https://keyserver.ubuntu.com/pks/lookup?fingerprint=on&op=get&search=0x6125E2A8C77F2818FB7BD15B93C4A3FD7BB9C367" | gpg --dearmour -o /usr/share/keyrings/ansible-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/ansible-archive-keyring.gpg] http://ppa.launchpad.net/ansible/ansible/ubuntu $UBUNTU_CODENAME main" | tee /etc/apt/sources.list.d/ansible.list
  apt-get update
  apt-get install --yes ansible python3-pip

  # "--ignore-installed" is added to fix error "Cannot uninstall PyYAML 6.0.2 ... The package was installed by debian."
  pip install passlib ansible-lint --ignore-installed --break-system-packages
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
    if [[ -f /etc/debian_version ]]; then
      if grep -qi ubuntu /etc/os-release; then
        install_ansible_on_ubuntu
      else
        install_ansible_on_debian
      fi
    else
      echo "Unknown Linux distribution."
      exit 1
    fi
    ;;
  darwin*)
    install_ansible_on_macos
    ;;
  *)
    echo "Platform not supported: $OSTYPE"
    exit 1
    ;;
esac
