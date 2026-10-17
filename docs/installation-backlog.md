# Installation improvement backlog

Installation procedures remain in [AWS installation](bootstrap-aws.md),
[Proxmox installation](setup.md) and [configuration and safety](bootstrap-configuration.md).
This backlog contains unresolved improvements, not alternate installation steps.

| Priority | Proposed improvement | Benefit | Dependencies and safeguards |
| --- | --- | --- | --- |
| Medium | Add an authorized read-only storage-readiness check that reports the exact owned volume's filesystem, blank-disk eligibility and previous-attempt status without printing infrastructure identifiers. | Helps operators diagnose storage safety failures before rerunning host configuration. | Use the original backend and existing safe-inspection conventions; never load service secrets, modify inputs, format storage or weaken the exact-volume checks. Document the distinction between offline inspection and live provider review, and add offline regression tests. |
