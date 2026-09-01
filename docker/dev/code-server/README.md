# code-server Authentik ForwardAuth

Authentik ForwardAuth limits browser access to code-server to Authentik's
`developers` group. Every authorized user reaches the same container,
workspace, repositories, and mounted SSH material; this is not a multi-user
authorization boundary.

## Setup

```bash
scripts/authentik-apps.py --application code-server --apply
scripts/labctl.py service recreate dev/code-server
```

Keep `localaccess-authentik@file` on the router and keep the service reachable
only through Traefik's `dev-code-server` network. Set `PASSWORD` or
`HASHED_PASSWORD` temporarily only when local recovery is necessary.

## Verify

Confirm authorized access, non-member denial, logout, session-refresh group
revocation, WebSocket/editor functionality, recovery, and absence of a direct
browser route.
