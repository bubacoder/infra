Code-server is VS Code running on a remote server, accessible through the browser.

Links:
- Home: [Coder | Enterprise AI Development Infrastructure & Governance](https://coder.com/)
- Image: [linuxserver/code-server - Docker Image](https://hub.docker.com/r/linuxserver/code-server)
- Source: [GitHub - coder/code-server: VS Code in the browser](https://github.com/coder/code-server)
- FAQ: [code-server/docs/FAQ.md at main · coder/code-server](https://github.com/coder/code-server/blob/main/docs/FAQ.md)

Alternative: OpenVSCode Server
- [GitHub - gitpod-io/openvscode-server: Run upstream VS Code on a remote machine with access through a modern web browser from any device, anywhere.](https://github.com/gitpod-io/openvscode-server)
- [OpenVSCode Server - LinuxServer.io](https://docs.linuxserver.io/images/docker-openvscode-server/)

# Authentik ForwardAuth

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
