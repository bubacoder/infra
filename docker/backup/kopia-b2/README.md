# Kopia B2 Authentik ForwardAuth

Authentik ForwardAuth is Kopia B2's browser access gate for the `admins` group.
Kopia's repository password remains separate from browser authentication. The
service depends on the isolated `backup-kopia` network and Traefik as its sole
UI path.

## Setup

```bash
scripts/authentik-apps.py --application kopia-b2 --apply
scripts/labctl.py service recreate backup/kopia-b2
```

Keep the router middleware as `localaccess-authentik@file`, Traefik connected to
`backup-kopia`, and no Kopia UI host port published. The current Kopia server
flags deliberately disable its own browser login because the network boundary
and ForwardAuth are required; do not reuse this configuration where direct
network access is possible.

## Verify

Confirm an `admins` member can use the UI, a non-member is denied, group removal
applies after session refresh, recovery works, and no direct container or host
path reaches the UI.
