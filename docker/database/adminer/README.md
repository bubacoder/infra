# Adminer Authentik ForwardAuth

Authentik ForwardAuth limits the Adminer browser UI to the `developers` group.
It is only an outer access gate: database-native credentials remain required.

## Setup

```bash
scripts/authentik-apps.py --application adminer --apply
scripts/labctl.py service recreate database/adminer
```

Keep the router middleware set to `localaccess-authentik@file` and do not
publish Adminer's HTTP port outside Traefik.

## Verify

Confirm a `developers` member reaches the Adminer database login screen, a
non-member is denied, database credentials are still required, and group
removal is applied after proxy-session refresh.
