# Onboarding Improvement Backlog

## Cloud-init recovery task

- Observed friction: if the provisioning task creates a VM but its final readiness check fails,
  rerunning it stops at the intentional VM-ID collision check.
- Proposed improvement: add a non-destructive task that waits for cloud-init on an existing VM
  and reports its status and recent failure details.
- Expected benefit: lets users distinguish a transient initialization delay from a failed
  configuration without recreating the VM.
- Decision or dependency: decide whether the task should also offer an explicitly confirmed
  cloud-init clean-and-reboot recovery action.
