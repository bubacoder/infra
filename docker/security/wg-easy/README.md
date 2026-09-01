# wg-easy Authentik OIDC

wg-easy v15 uses native OIDC for Authentik's `admins` group. WireGuard peer keys
and UDP traffic remain independent of browser SSO. Traefik still limits the UI
to LAN/VPN through `localaccess@file`.

## Setup

Set `WG_EASY_AUTHENTIK_CLIENT_ID` and `WG_EASY_AUTHENTIK_CLIENT_SECRET` in
ignored host configuration, then create the Authentik application:

```bash
scripts/authentik-apps.py --application wg-easy --apply
scripts/labctl.py service recreate security/wg-easy
```

Password authentication remains disabled. Before starting wg-easy, ensure an
administrator can complete OIDC login through Authentik. For a v14 migration,
import `wg0.json` into a separate v15 state directory and verify OIDC access
before retiring the v14 deployment. Never mount v15 over the v14 state; retain
v14 data as the rollback source.

The registered callbacks are `https://vpn.<domain>/api/auth/oidc/callback` and
`https://vpn.<domain>/api/auth/oidc/link`.

## Future Hardening

The current OIDC mapping marks every Authentik user's email as verified. Before
relying on email-based account linking beyond the initial administrator setup,
consider creating a dedicated `wg-easy-email-verified` Authentik group and
emitting `email_verified: true` only for its members. This makes email
verification an explicit, reviewable approval rather than trusting every local
or break-glass account.

## Verify

Confirm an `admins` member can sign in through OIDC, a non-member is denied,
the imported peers remain intact, and WireGuard clients continue connecting.
