# Ansible

https://www.ansible.com/

> Automation for everyone
> No matter your role, or what your automation goals are, Ansible can help you demonstrate value, connect teams, and deliver efficiencies for your organization.
> Built on open source, Red Hat® Ansible® Automation Platform is a hardened, tested subscription product that offers full life cycle support for organizations. Explore how Ansible can help you automate today—and scale for the future.

## Tutorials, Resources

- [Learn Linux TV - Getting started with Ansible](https://www.youtube.com/playlist?list=PLT98CRl2KxKEUHie1m24-wkyHpEsa4Y70)
- [Laying out roles, inventories and playbooks](https://leucos.github.io/ansible-files-layout)
- [An evolving set of mac user creation, setup and maintenance playbooks being used at Ideas On Purpose](https://github.com/ideasonpurpose/ansible-playbooks)
- [Variable precedence: Where should I put a variable?](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html#variable-precedence-where-should-i-put-a-variable)

## Directory structure

- `ansible` -- Configuration of the host OS & required software
  - `ansible/roles` -- Roles for Debian-based Docker & admin hosts and a Mac-based DevOps/SRE toolset
  - `ansible/playbooks` -- Host-role assignments. The playbooks can be executed with the `apply-*.sh` scripts
  - `ansible/inventory` -- Host specific environment configuration

## Setup steps

1. Install Ansible on the admin workstation with `bootstrap-ansible.sh`. (See: [Ansible control node](https://docs.ansible.com/ansible/latest/network/getting_started/basic_concepts.html#control-node))
2. Configure variables in `inventory/group_vars/`
3. Add hosts to `inventory/inventory.yaml`
4. Assign roles to hosts in `playbooks/`
5. Run `apply-<playbook>.sh` to execute a playbook
   - If you use a non-root user and `sudo` requires a password (indicated by the "Missing sudo password" error message), use `apply-<playbook>.sh --ask-become-pass` and specify the password when requested ("BECOME password" message)
   - The playbook will set up passwordless `sudo`, so next time the `--ask-become-pass` parameter will not be required
6. When the administrative user is already created, use that user in the inventory instead of `root` (`ansible_user: <adminuser>`). This is more secure and also required by Homebrew.

## Bootstrapping hosts with authentication

1. Copy public SSH key, e.g.:
   `ssh-copy-id -i ~/.ssh/id_ed25519.pub root@192.168.1.50`
2. Run playbook with existing user (`root` or your admin user if already created)
3. Verify the connection with: `ansible all -m ping`

## Useful options

The following parameters can be applied to `ansible-playbook` and the "apply..." scripts.

- `-l`, `--limit` - Limit Ansible run for a specific host (or host group). Example: `./apply-homelab.sh --limit <host>`
- `-v`, `--verbose` - Causes Ansible to print more debug messages. Adding multiple -v will increase the verbosity, the builtin plugins currently evaluate up to -vvvvvv. A reasonable level to start is -vvv, connection debugging might require -vvvv. Example: `./apply-homelab.sh -v`

See `man ansible-playbook` for more.

## GUI

https://github.com/ansible/awx

> ansible/awx: AWX provides a web-based user interface, REST API, and task engine built on top of Ansible. It is one of the upstream projects for Red Hat Ansible Automation Platform.
