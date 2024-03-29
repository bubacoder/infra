
# Cloud-init

> Cloud-init is the industry standard multi-distribution method for cross-platform cloud instance initialisation. It is supported across all major public cloud providers, provisioning systems for private cloud infrastructure, and bare-metal installations.

[Official documentation](https://cloudinit.readthedocs.io/en/latest/),
[Terraform provider](https://registry.terraform.io/providers/hashicorp/cloudinit/latest/docs/resources/config)

## Debugging tips

Location of the scripts on the target system: `/var/lib/cloud/instance/scripts`

Logs:

```bash
cat /var/log/cloud-init-output.log
cat /var/log/cloud-init.log
```

For the execution order of the modules, check [cloud.cfg.tmpl](https://git.launchpad.net/cloud-init/tree/config/cloud.cfg.tmpl)
