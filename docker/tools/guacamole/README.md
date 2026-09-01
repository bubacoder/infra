# Guacamole Authentik OIDC

Guacamole uses native OIDC for Authentik's `admins` group and its embedded
PostgreSQL database for local recovery and connection permissions. Do not remove
the JDBC extension or retained local administrator.

## Setup

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

## Verify

An `admins` member must authenticate through OIDC and a non-member must be
denied. OIDC identities are created as JDBC users without connection
permissions; assign only required groups and connections with the local
administrator. Verify local recovery, SSH/RDP/VNC connections, logout, and
session expiry.
