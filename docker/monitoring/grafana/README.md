# Grafana Authentik OIDC

Grafana uses native OIDC for Authentik's `monitoring` group. Keep a local
Grafana administrator enabled for recovery. API tokens and service accounts are
independent of browser SSO.

## Setup

Create the ignored client-secret file:

```text
config/docker/<host>/grafana/authentik-client-secret
```

Set its mode to `0600`, then set `GRAFANA_AUTHENTIK_CLIENT_ID` and
`GRAFANA_AUTHENTIK_CLIENT_SECRET_PATH` in the ignored host `.env` file. Create
the Authentik resources and recreate Grafana:

```bash
scripts/authentik-apps.py --application grafana --apply
scripts/labctl.py service recreate monitoring/grafana
```

The Compose configuration supplies the issuer endpoints, PKCE, refresh-token
scope, and sign-out endpoint. Keep the registered callback URI exact:
`https://grafana.<domain>/login/generic_oauth`.

## Verify

Confirm a `monitoring` member can sign in, a non-member is denied, and the
retained local administrator can still sign in. Access changes are re-evaluated
when Grafana refreshes its Authentik token.
