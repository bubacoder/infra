SHELL := /bin/bash

VMRGNAME?=HomeInfra
VMNAME?=nest
KEYFILE?=nest_id_rsa
FQDN?=buba-nest.westeurope.cloudapp.azure.com

.PHONY: clean
clean:
	find . -type d -name '.terraform' -exec rm -rf {} +

.PHONY: docs
docs:
	echo 'updating terraform module documentation'
	find . -name 'README.md' -not -path '*/.terragrunt-cache/*' -execdir terraform-docs markdown table --output-file README.md --output-mode inject . \;

.PHONY: check
check:
	terraform validate && tfsec

.PHONY: plan
plan:
	terraform plan

.PHONY: apply
apply:
	time terraform apply --auto-approve
	terraform output -raw tls_private_key > ${KEYFILE} && chmod 600 ${KEYFILE}
	sed -i '' '/buba\-nest\.westeurope\.cloudapp\.azure\.com/d' ~/.ssh/known_hosts

.PHONY: destroy
destroy:
	time terraform destroy --auto-approve && rm ${KEYFILE}

.PHONY: destroy-vm
destroy-vm:
	time terraform destroy --auto-approve --target module.nest.azurerm_linux_virtual_machine.nest && rm ${KEYFILE}

.PHONY: connect
connect:
	ssh -i ${KEYFILE} azureuser@${FQDN}

# .PHONY: connect-port
# connect-port:
# 	ssh -i ${KEYFILE} azureuser@${FQDN} -L 9000:localhost:9000

.PHONY: start-vm
start-vm:
	az vm start -g ${VMRGNAME} -n ${VMNAME}

.PHONY: stop-vm
stop-vm:
	az vm stop -g ${VMRGNAME} -n ${VMNAME}
