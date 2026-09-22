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

Code-server is VS Code running on a remote server, accessible through the browser.

Links:
- Home: https://coder.com/
- Image: https://hub.docker.com/r/linuxserver/code-server
- Source: https://github.com/coder/code-server
- FAQ: https://github.com/coder/code-server/blob/main/docs/FAQ.md

Alternative: OpenVSCode Server
- https://github.com/gitpod-io/openvscode-server
- https://docs.linuxserver.io/images/docker-openvscode-server/
