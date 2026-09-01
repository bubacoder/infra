# Obsidian Authentik ForwardAuth

Authentik ForwardAuth limits access to the browser-hosted Obsidian desktop to
the `admins` group. All admitted users share the same desktop, vault, terminal,
and container privileges; it is not a multi-user authorization boundary.

## Setup

```bash
scripts/authentik-apps.py --application obsidian --apply
scripts/labctl.py service recreate tools/obsidian
```

Keep `localaccess-authentik@file` on the router and the UI port private to
Traefik. `OBSIDIAN_CUSTOM_USER` and `OBSIDIAN_PASSWORD` provide a temporary
native recovery path when configured through ignored host values.

## Verify

Confirm authorized access, non-member denial, logout, session-refresh group
revocation, local recovery, and absence of a direct browser route.
