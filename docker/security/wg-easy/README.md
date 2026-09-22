# wg-easy Authentik OIDC

wg-easy v15 uses native OIDC for Authentik's `admins` group. WireGuard peer keys
and UDP traffic remain independent of browser SSO. Traefik still limits the UI
to LAN/VPN through `localaccess@file`.

## Setup

Set `WG_EASY_AUTHENTIK_CLIENT_ID` and `WG_EASY_AUTHENTIK_CLIENT_SECRET` in
ignored `config/docker/<host>/.env.wg-easy`, then create the Authentik
application:

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

WireGuard® is an extremely simple yet fast and modern VPN that utilizes state-of-the-art cryptography. It aims to be faster, simpler, leaner, and more useful than IPsec, while avoiding the massive headache.
It intends to be considerably more performant than OpenVPN. WireGuard is designed as a general purpose VPN for running on embedded interfaces and super computers alike, fit for many different circumstances.
Initially released for the Linux kernel, it is now cross-platform (Windows, macOS, BSD, iOS, Android) and widely deployable. It is currently under heavy development,
but already it might be regarded as the most secure, easiest to use, and simplest VPN solution in the industry.

Android - configure application exclusion, e.g. Android Auto: Open the Wireguard app, edit the profile, click "All Applications", select the application you want to exclude.

Links:
- Home: https://www.wireguard.com/
- Source: https://github.com/wg-easy/wg-easy
- Migration Guide: [Migrate from v14 to v15](https://wg-easy.github.io/wg-easy/latest/advanced/migrate/from-14-to-15/)
