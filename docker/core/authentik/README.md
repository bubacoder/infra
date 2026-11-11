# Authentik

This directory contains the Authentik Compose definition and tracked
blueprints. For the one-time deployment, break-glass administrator, MFA,
recovery, Google federation, and backup procedure, read
[`docs/authentik.md`](../../../docs/authentik.md).

## References

- Home: [Welcome | authentik](https://goauthentik.io/)
- Source: [GitHub - goauthentik/authentik: The authentication glue you need.](https://github.com/goauthentik/authentik)
- Docs: [Welcome to authentik | authentik](https://docs.goauthentik.io/)
- Docker Compose: [Docker Compose installation | authentik](https://docs.goauthentik.io/install-config/install/docker-compose/)

## Host Secrets

Create the ignored `config/docker/<host>/authentik/` directory and generate the
required secret files:

```bash
mkdir -p config/docker/<host>/authentik
openssl rand -out config/docker/<host>/authentik/postgresql-password -base64 36
openssl rand -out config/docker/<host>/authentik/secret-key -hex 60
chmod 600 config/docker/<host>/authentik/postgresql-password config/docker/<host>/authentik/secret-key
```

Set `AUTHENTIK_SECRETS_PATH` in `config/docker/<host>/.env.authentik` to this
directory. Do not commit the generated files.

## Application SSO

For adding or migrating applications to Authentik, read
[`app-onboarding.md`](app-onboarding.md).

Authentik is an identity provider and SSO platform supporting OIDC, OAuth2,
SAML, LDAP, social login sources, and proxy authentication outposts.

The embedded proxy outpost is used, so the worker does not need access to the
Docker socket. Do not change the sso hostname after configuring OIDC clients;
it forms part of the permanent issuer URL.

## Backup

`backup.yaml` defines nightly PostgreSQL database/role exports under
`${DB_BACKUP_ROOT}/security-authentik/`. Restore with Authentik's
data, templates, certificates and **original secret key**; recover identity before
dependent SSO applications. See the [backup guide](../../../docs/backup.md)
for export commands, B2 coverage, retention and snapshot selection.

### Recovery

1. Recover `database.dump`, `globals.sql` and the manifest. With server/worker
   stopped, restore required roles and the `authentik` database into a compatible
   dedicated PostgreSQL destination with the original ownership.
2. Restore `${DOCKER_VOLUMES}/authentik/{data,certs,templates}`, tracked
   blueprints/Compose configuration and original ignored `authentik/secret-key`
   and `authentik/postgresql-password`. Preserve signing keys, OIDC settings and
   the issuer hostname; do not generate replacement setup secrets for a restore.
3. Start PostgreSQL, then the matching Authentik server/worker images. Recover
   identity access before starting dependent SSO applications.

The DB export does not inventory every required application file automatically;
confirm these files/secrets exist in the selected recovery copies.

### Post-restore check

Restore the original secret key and paired state with the PostgreSQL dump. Check
container health, sign in with the retained local administrator, and confirm one
dependent application's OIDC login. Keep the original issuer hostname.
