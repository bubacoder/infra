# Makefile Cheat Sheet: https://bytes.usc.edu/cs104/wiki/makefile

SHELL := /bin/bash
RESOURCE_GROUP := HomeInfra

VM_NAME := nest
VM_KEYFILE := ~/.ssh/id_rsa_azure_nest
VM_FQDN := buba-nest.westeurope.cloudapp.azure.com

OWN_PUBLIC_IP ?= $(shell curl -s https://ipinfo.io/ip)
GIT_CREDENTIALS ?= $(shell cat ~/.git-credentials | head -n 1)
REPO_URL ?= $(shell git config --get remote.origin.url)


.PHONY: clean
clean:
	find . -type d -name '.terraform' -exec rm -rf {} +

.PHONY: docs
docs:
	@echo 'Updating Terraform module documentation'
	find . -name 'README.md' -not -path '*/.terragrunt-cache/*' -execdir terraform-docs markdown table --output-file README.md --output-mode inject . \;

.PHONY: check
check:
	terraform validate && tfsec

.PHONY: plan
plan:
	terraform plan -var="admin_source_address=${OWN_PUBLIC_IP}" -var="git_credentials=${GIT_CREDENTIALS}" -var="repo_url=${REPO_URL}" -out="tfplan"

.PHONY: apply
apply: plan
	time terraform apply --auto-approve "tfplan"
	ssh-keygen -f ~/.ssh/known_hosts -R "${VM_FQDN}" && terraform output -raw tls_private_key > ${VM_KEYFILE} && chmod 600 ${VM_KEYFILE}

.PHONY: destroy
destroy:
	time terraform destroy --auto-approve -var="admin_source_address=${OWN_PUBLIC_IP}" -var="git_credentials=${GIT_CREDENTIALS}" -var="repo_url=${REPO_URL}" && rm ${VM_KEYFILE}

.PHONY: destroy-vm
destroy-vm:
	time terraform destroy --auto-approve -var="admin_source_address=${OWN_PUBLIC_IP}" -var="git_credentials=${GIT_CREDENTIALS}" -var="repo_url=${REPO_URL}" --target module.nest.azurerm_linux_virtual_machine.nest && rm ${VM_KEYFILE}

.PHONY: connect
connect:
	ssh -i ${VM_KEYFILE} azureuser@${VM_FQDN}

.PHONY: start-vm
start-vm:
	az vm start -g ${RESOURCE_GROUP} -n ${VM_NAME}

.PHONY: stop-vm
stop-vm:
	az vm stop -g ${RESOURCE_GROUP} -n ${VM_NAME}

.PHONY: deallocate-vm
deallocate-vm:
	az vm deallocate -g ${RESOURCE_GROUP} -n ${VM_NAME}
