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

Adminer is a full-featured database management tool written in PHP that consists
of a single file ready to deploy to the target server. It supports MySQL, MariaDB,
PostgreSQL, CockroachDB, SQLite, MS SQL, Oracle, and through plugins: Elasticsearch,
SimpleDB, MongoDB, Firebird, ClickHouse, and IMAP systems.

Links:
- Home: https://www.adminer.org
- Source: https://github.com/vrana/adminer
- Docs: https://hub.docker.com/_/adminer/

TODO: Enable custom plugins via ADMINER_PLUGINS environment variable
TODO: Consider mounting custom CSS themes for UI customization
TODO: Create dedicated database network for secure database connections
