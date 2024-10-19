# Makefile Cheat Sheet: https://bytes.usc.edu/cs104/wiki/makefile

# Note: An alternative for 'Makefile' is 'Taskfile'.
#   See: https://taskfile.dev/, https://www.youtube.com/watch?v=Z7EnwBaJzCk

SHELL := /bin/bash

# Select "terraform" or "tofu"
TFBIN := terraform
# Use "." for the current directory
CONFIG_DIR := ../config/terraform

TFPLAN := $(CONFIG_DIR)/tfplan
VAR_FILE := $(CONFIG_DIR)/infra.tfvars

# TODO Read params from tfvars
RESOURCE_GROUP := HomeInfra
VM_NAME := nest
VM_KEYFILE := ~/.ssh/id_rsa_azure_vm
VM_FQDN ?= $(shell ${TFBIN} output -raw vm_fqdn)
VM_ADMIN_USER := azureuser

OWN_PUBLIC_IP ?= $(shell curl -s https://ipinfo.io/ip)
GIT_CREDENTIALS ?= $(shell cat ~/.git-credentials | head -n 1)
REPO_URL ?= $(shell git config --get remote.origin.url)
VAR_PARAMETERS ?= -var-file="${VAR_FILE}" -var="admin_source_address=${OWN_PUBLIC_IP}" -var="git_credentials=${GIT_CREDENTIALS}" -var="repo_url=${REPO_URL}"

export TF_IN_AUTOMATION = 1

.PHONY: clean
clean:
	find . -type d -name '.terraform' -exec rm -rf {} +

.PHONY: docs
docs:
	@echo 'Updating Terraform module documentation'
	find . -name 'README.md' -not -path '*/.terragrunt-cache/*' -execdir terraform-docs markdown table --output-file README.md --output-mode inject . \;

.PHONY: check
check:
	${TFBIN} validate && tfsec

.PHONY: plan
plan:
	${TFBIN} init
	@echo "${TFBIN} plan..."
	@${TFBIN} plan ${VAR_PARAMETERS} -out="${TFPLAN}"

.PHONY: apply
apply: plan
	@echo "${TFBIN} apply..."
	@time ${TFBIN} apply --auto-approve "${TFPLAN}"
	ssh-keygen -f ~/.ssh/known_hosts -R "${VM_FQDN}" && ${TFBIN} output -raw vm_tls_private_key > ${VM_KEYFILE} && chmod 600 ${VM_KEYFILE}

# TODO Use provisioner: https://www.udemy.com/course/terraform-hands-on-labs/learn/lecture/29614642#overview

.PHONY: destroy
destroy:
	@echo "${TFBIN} destroy..."
	@${TFBIN} destroy --auto-approve ${VAR_PARAMETERS} && rm ${VM_KEYFILE}

.PHONY: destroy-vm
destroy-vm:
	@echo "${TFBIN} destroy..."
	@${TFBIN} destroy --auto-approve ${VAR_PARAMETERS} --target module.vm.azurerm_linux_virtual_machine.vm && rm ${VM_KEYFILE}

.PHONY: connect-vm
connect-vm:
	ssh -i ${VM_KEYFILE} ${VM_ADMIN_USER}@${VM_FQDN}

.PHONY: config-vm
config-vm:
	cd ../ansible; ./apply-cloud.sh

.PHONY: start-vm
start-vm:
	az vm start -g ${RESOURCE_GROUP} -n ${VM_NAME}

.PHONY: stop-vm
stop-vm:
	az vm stop -g ${RESOURCE_GROUP} -n ${VM_NAME}

.PHONY: deallocate-vm
deallocate-vm:
	az vm deallocate -g ${RESOURCE_GROUP} -n ${VM_NAME}
