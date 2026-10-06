Apache Guacamole is a clientless remote desktop gateway. It supports standard protocols like VNC and RDP. We call it clientless because no plugins or client software are required.

Thanks to HTML5, once Guacamole is installed on a server, all you need to access your desktops is a web browser.

The default username is `guacadmin` with password `guacadmin`.

## References

- Home: [Apache Guacamole®](https://guacamole.apache.org/)
- Image: [flcontainers/guacamole - Docker Image](https://hub.docker.com/r/flcontainers/guacamole)

## Authentik

Guacamole uses native OIDC for Authentik's `admins` group and its embedded
PostgreSQL database for local recovery and connection permissions. Do not remove
the JDBC extension or retained local administrator.

### Setup

Back up `${DOCKER_VOLUMES}/guacamole`, including its embedded database. Set the
following non-secret values in ignored `config/docker/<host>/.env.guacamole`:

```dotenv
GUACAMOLE_AUTHENTIK_CLIENT_ID=guacamole
GUACAMOLE_AUTHENTIK_SIGNING_KEY=<asymmetric Authentik signing-key UUID>
```

Create the Authentik provider, update Guacamole's persisted OIDC properties,
then recreate the service:

```bash
scripts/authentik-apps.py --application guacamole --apply
docker/tools/guacamole/guacamole-oidc.py --host <host> --apply
scripts/labctl.py service recreate tools/guacamole
```

The public implicit provider callback is exactly `https://guacamole.<domain>`
without a trailing slash.

### Verify

An `admins` member must authenticate through OIDC and a non-member must be
denied. OIDC identities are created as JDBC users without connection
permissions; assign only required groups and connections with the local
administrator. Verify local recovery, SSH/RDP/VNC connections, logout, and
session expiry.

## Backup

`backup.yaml` exports the image's **embedded PostgreSQL 13**, not shared
PostgreSQL, nightly to `${DB_BACKUP_ROOT}/tools-guacamole/`. Pair it
with `/config/guacamole` properties, extensions/libraries and original host/OIDC
settings from the verified application B2 snapshot. See the
[backup guide](../../../docs/backup.md) for commands, retention and snapshot selection.

### Recovery

1. Recover `database.dump`, sensitive `globals.sql` and the manifest. Restore
   required roles and database `guacamole_db` with its original owner `guacamole`
   into a compatible **embedded PostgreSQL 13** destination before admitting
   frontend clients. This is not a restore into the shared PostgreSQL service.
2. Restore `/config/guacamole/guacamole.properties`, `extensions/` and `lib/`, plus
   the preserved PostgreSQL `*.conf` files and original host/OIDC configuration.
   Keep copied old `/config/postgres` raw data separate from the logical DB restore.
3. Preserve the matching image's `postgres`/`tomcat` access to restored files.
   Start the application with JDBC and its existing local recovery administrator;
   do not recreate initial accounts as a substitute for restoring permissions.

An archive/table check alone does not establish successful frontend recovery;
validate the login and connection workflow below, including restored roles.

### Post-restore check

Restore the embedded DB and paired properties/extensions, check health, sign in
with the existing account and open one known SSH/RDP/VNC connection. Confirm its
connection permissions survived.
