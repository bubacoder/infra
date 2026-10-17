# Onboarding Improvement Backlog

## Multiple VM configurations

- Observed friction: `task bootstrap:vm-init` uses one fixed
  `config/vm/proxmox/ubuntu-cloud.env`; an existing test VM configuration had to be edited for the
  next VM even though both may need to remain manageable.
- Proposed improvement: accept a configuration name or path and generate one file per VM.
- Expected benefit: avoids destroying prior deployment intent and enables parallel test profiles.
- Decision or dependency: choose the naming convention and whether VM ID or hostname is the
  primary key.

## DHCP reservation integration

- Observed friction: DHCP reservations remain externally managed even though DNS
  can now be reconciled automatically after guest address discovery.
- Proposed improvement: support selected router DHCP APIs for reservation previews.
- Expected benefit: stable addresses without an extra router-side manual step.
- Decision or dependency: select supported routers and require explicit approval
  before replacing any existing reservation.

## Resolved in code: target-aware DNS integration

- [Managed DNS](bootstrap-dns.md) now supports optional AdGuard for both targets
  and defaults to Cloudflare address records for AWS. Parent records and DDNS remain
  untouched. The obsolete hosts-file helpers were removed.
- Offline regression coverage exists; live provider writes and deployment resume
  still require configuration, approval and revalidation. This is not a claim of
  completed live installation.

## Proxmox thin-pool guardrails

- Observed friction: provisioning continued after warning that the thin pool was overcommitted and
  could not autoextend, while the read-only preflight reported success.
- Proposed improvement: report physical usage, virtual overcommit, and autoextend policy in
  preflight with configurable warn/fail thresholds before creating a disk.
- Expected benefit: makes storage risk visible before allocation and avoids preventable outages.
- Decision or dependency: define acceptable overcommit and autoextend policies for each target.
