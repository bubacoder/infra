# Onboarding Improvement Backlog

## Multiple VM configurations

- Observed friction: `task bootstrap:vm-init` uses one fixed
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
- Proposed improvement: optionally support selected router/DNS providers in addition to the
  bootstrap preflight that verifies user-managed reservations and wildcard resolution.
- Expected benefit: removes the remaining manual external step without silently routing users to
  the wrong host.
- Decision or dependency: select supported DHCP/DNS systems and require explicit approval before
  replacing an existing record or reservation.

## Proxmox thin-pool guardrails

- Observed friction: provisioning continued after warning that the thin pool was overcommitted and
  could not autoextend, while the read-only preflight reported success.
- Proposed improvement: report physical usage, virtual overcommit, and autoextend policy in
  preflight with configurable warn/fail thresholds before creating a disk.
- Expected benefit: makes storage risk visible before allocation and avoids preventable outages.
- Decision or dependency: define acceptable overcommit and autoextend policies for each target.

## Proxmox command locale warnings

- Observed friction: every Proxmox CLI call emitted repeated Perl locale warnings, obscuring bootstrap progress and failures.
- Proposed improvement: run bootstrap's remote Proxmox commands with a stable `C` locale or document the required Proxmox locale configuration.
- Expected benefit: clearer deployment diagnostics without changing host resources or service behavior.
- Decision or dependency: choose whether locale normalization belongs in bootstrap commands or Proxmox host configuration.
