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

A powerful knowledge base that works on top of a local folder of plain text Markdown files.
Obsidian is a free and flexible app for your private thoughts that stores notes locally
with extensive plugin support and open file formats.

Links:
- Home: https://obsidian.md
- Source: https://github.com/obsidianmd
- Docs: https://docs.linuxserver.io/images/docker-obsidian/

TODO: Set up regular backups of the /config/vaults volume containing vault data
TODO: Consider GPU acceleration configuration if needed for advanced use cases
