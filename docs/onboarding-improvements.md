# Onboarding Improvement Backlog

## Deployment preflight task

- Observed friction: first-time provisioning requires manual checks for VM ID availability,
  Proxmox storage/bridge availability, SSH access, and required administrative-host tools.
- Proposed improvement: add a read-only `task` preflight that validates these inputs before VM
  creation and reports actionable failures.
- Expected benefit: reduces failed or partial VM provisioning and makes the required values
  discoverable at the point of use.
- Decision or dependency: the task needs a documented policy for the acceptable thin-pool
  headroom and whether a static DHCP reservation is mandatory.

## Minimal service profile

- Observed friction: the supplied example enables a large service set, while the setup guide does
  not define a safe minimum deployment.
- Proposed improvement: provide a reviewed minimal service profile and a generator that creates
  only its required ignored configuration files.
- Expected benefit: prevents accidental deployment of unrelated services and exposes required
  external integrations before containers are started.
- Decision or dependency: define whether Traefik requires CrowdSec and Cloudflare DNS for the
  supported minimum profile.
