WireGuard® is an extremely simple yet fast and modern VPN that utilizes state-of-the-art cryptography. It aims to be faster, simpler, leaner, and more useful than IPsec, while avoiding the massive headache.
It intends to be considerably more performant than OpenVPN. WireGuard is designed as a general purpose VPN for running on embedded interfaces and super computers alike, fit for many different circumstances.
Initially released for the Linux kernel, it is now cross-platform (Windows, macOS, BSD, iOS, Android) and widely deployable. It is currently under heavy development,
but already it might be regarded as the most secure, easiest to use, and simplest VPN solution in the industry.

Android - configure application exclusion, e.g. Android Auto: Open the Wireguard app, edit the profile, click "All Applications", select the application you want to exclude.

## References

- Home: https://www.wireguard.com/
- Source: [GitHub - wg-easy/wg-easy: The easiest way to run WireGuard VPN + Web-based Admin UI.](https://github.com/wg-easy/wg-easy)
- Migration Guide: [Migrate from v14 to v15](https://wg-easy.github.io/wg-easy/latest/advanced/migrate/from-14-to-15/)

## Authentik

wg-easy v15 uses native OIDC for Authentik's `admins` group. WireGuard peer keys
and UDP traffic remain independent of browser SSO. Traefik still limits the UI
to LAN/VPN through `localaccess@file`.

### Setup

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

### Future Hardening

The current OIDC mapping marks every Authentik user's email as verified. Before
relying on email-based account linking beyond the initial administrator setup,
consider creating a dedicated `wg-easy-email-verified` Authentik group and
emitting `email_verified: true` only for its members. This makes email
verification an explicit, reviewable approval rather than trusting every local
or break-glass account.

### Verify

Confirm an `admins` member can sign in through OIDC, a non-member is denied,
the imported peers remain intact, and WireGuard clients continue connecting.

## Backup

`backup.yaml` exports `wg-easy-v15/wg-easy.db` online each night under
`${DB_BACKUP_ROOT}/security-wg-easy/`, preserving accounts, OIDC links,
server/peer keys and interface settings without interrupting the VPN. B2 pairs
it with `wg0.conf`; restore original `.env.wg-easy`/Authentik settings and keys.
See the [backup guide](../../../docs/backup.md) for commands, retention and snapshot selection.

### Recovery

1. Stop only the destination wg-easy. Restore the standalone `database.sqlite3`
   as `${DOCKER_VOLUMES}/wg-easy-v15/wg-easy.db`, removing stale destination WAL/SHM.
2. Restore paired `wg0.conf`, original ignored `.env.wg-easy`/OIDC settings and
   ownership, then start the matching v15 image. Restore Authentik access first
   when password authentication is disabled.
3. The database is authoritative and interface configuration is regenerated;
   do not rerun initial setup or generate new server/peer keys. Preserve v14
   rollback state separately rather than mounting v15 over it.

### Post-restore check

Confirm the peers and server public key recorded by the selected backup, sign in through
OIDC, and connect one existing WireGuard client. Check its handshake and LAN access.
