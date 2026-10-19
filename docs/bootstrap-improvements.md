# Bootstrap improvement backlog

Open onboarding improvements; the installation guides remain the source of truth.

| Priority | Improvement | Benefit | Dependencies |
| --- | --- | --- | --- |
| Medium | Extend Proxmox preflight to report physical free space, thin-pool data/metadata health, and configured disk/memory demand. Keep overcommit decisions explicit rather than silently permitting or rejecting them. | Makes the manual capacity checkpoint in the [Proxmox guide](setup.md#operational-limits) easier to complete before provisioning. | Storage-type-aware read-only checks and an agreed capacity/overcommit policy. |
| Low | Provide an offline controller prerequisite check for executables and the pinned Ansible collections. | Identifies missing or shadowed dependencies before initialization or live preflight. | Follow the prerequisite lists in the installation guides and collection versions in `ansible/requirements.yml`; do not install dependencies implicitly. |
