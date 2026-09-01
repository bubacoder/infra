# Authentik

This directory contains the Authentik Compose definition and tracked
blueprints. For the one-time deployment, break-glass administrator, MFA,
recovery, Google federation, and backup procedure, read
[`docs/authentik.md`](../../../docs/authentik.md).

## Host Secrets

Create the ignored `config/docker/<host>/authentik/` directory and generate the
required secret files:

```bash
openssl rand -out postgresql-password -base64 36
openssl rand -out secret-key -hex 60
chmod 600 postgresql-password secret-key
```

Set `AUTHENTIK_SECRETS_PATH` in the host `.env` to this directory. Do not
commit the generated files.

## Application SSO

For adding or migrating applications to Authentik, read
[`app-onboarding.md`](app-onboarding.md).
