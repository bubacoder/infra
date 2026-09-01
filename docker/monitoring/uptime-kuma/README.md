# Uptime Kuma Authentik ForwardAuth

Uptime Kuma has no native OIDC configuration. Traefik protects its browser UI
with Authentik ForwardAuth for the `monitoring` group. Do not publish its UI
port outside the proxy network.

## Setup

Create the Authentik application and provider, then deploy the service:

```bash
scripts/authentik-apps.py --application uptime-kuma --apply
scripts/labctl.py service recreate monitoring/uptime-kuma
```

The service label must use `localaccess-authentik@file`; the shared Traefik
configuration routes `/outpost.goauthentik.io/` for the application hostname.

## Verify

Confirm a `monitoring` member reaches the UI and live updates work. Confirm a
non-member is denied, group removal is applied after the proxy session refresh,
logout returns to the intended login flow, and no direct UI path exists.
