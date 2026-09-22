# Authentik

This directory contains the Authentik Compose definition and tracked
blueprints. For the one-time deployment, break-glass administrator, MFA,
recovery, Google federation, and backup procedure, read
[`docs/authentik.md`](../../../docs/authentik.md).

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

Links:
- Home: https://goauthentik.io/
- Source: https://github.com/goauthentik/authentik
- Docs: https://docs.goauthentik.io/
- Docker Compose: https://docs.goauthentik.io/install-config/install/docker-compose/
