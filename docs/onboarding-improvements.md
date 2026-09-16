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

## Declarative bootstrap configuration

- Observed friction: the tested path required repeatedly copying the same VM, inventory, domain,
  email, storage, service-profile, and host values into separate files and commands.
- Proposed improvement: add one non-secret bootstrap YAML and a Python orchestrator with explicit
  plan/apply phases for generating ignored configuration, provisioning the VM, running Ansible,
  configuring the remote `bootstrap` checkout, deploying core services, and verifying readiness.
  Use the observed input contract in [Bootstrap Configuration Draft](bootstrap-configuration.md).
- Expected benefit: removes manual transcription, preserves a reviewable deployment contract, and
  makes ordering, validation, retries, and failure recovery reproducible.
- Decision or dependency: define secret references or interactive handoff without placing secret
  values in YAML, and decide which router/DNS integrations the orchestrator may change.

## Multiple VM configurations

- Observed friction: `task vm:ubuntu-cloud-init` uses one fixed
  `config/vm/proxmox/ubuntu-cloud.env`; an existing test VM configuration had to be edited for the
  next VM even though both may need to remain manageable.
- Proposed improvement: accept a configuration name or path and generate one file per VM.
- Expected benefit: avoids destroying prior deployment intent and enables parallel test profiles.
- Decision or dependency: choose the naming convention and whether VM ID or hostname is the
  primary key.

## DHCP and local DNS integration

- Observed friction: provisioning reports a DHCP address, but lease reservation and wildcard DNS
  remain manual external steps; during this test DNS resolved the service names to another host,
  requiring temporary concrete `/etc/hosts` entries on the admin environment.
- Proposed improvement: add a post-provision network checkpoint that verifies reservation and
  base/wildcard resolution, supports pluggable router/DNS providers, and clearly offers a temporary
  hosts-file fallback for named core endpoints.
- Expected benefit: prevents a healthy deployment from silently routing users to the wrong host.
- Decision or dependency: select supported DHCP/DNS systems and require explicit approval before
  replacing an existing record or reservation.

## Proxmox thin-pool guardrails

- Observed friction: provisioning continued after warning that the thin pool was overcommitted and
  could not autoextend, while the read-only preflight reported success.
- Proposed improvement: report physical usage, virtual overcommit, and autoextend policy in
  preflight with configurable warn/fail thresholds before creating a disk.
- Expected benefit: makes storage risk visible before allocation and avoids preventable outages.
- Decision or dependency: define acceptable overcommit and autoextend policies for each target.

## Automated service acceptance

- Observed friction: `task docker:apply` starts containers but does not wait for certificate
  issuance or verify container stability, HTTPS routes, DNS targets, persistence, or repeat safety.
- Proposed improvement: add a bounded `docker:verify` task for the selected host profile.
- Expected benefit: provides one repeatable acceptance check and actionable failure evidence.
- Decision or dependency: define per-service health and access expectations without embedding
  credentials in commands or logs.
