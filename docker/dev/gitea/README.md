# Gitea Authentik OIDC

Gitea uses native OIDC for Authentik's `developers` group. Browser SSO does not
replace Git-over-SSH keys, Git HTTPS personal access tokens, or runner tokens.
Keep a local Gitea administrator for recovery.

## Setup

Create the ignored secret file at
`config/docker/<host>/gitea/authentik-client-secret` with mode `0600`. Set
`GITEA_AUTHENTIK_CLIENT_ID`, `GITEA_AUTHENTIK_CLIENT_SECRET`, and
`GITEA_AUTHENTIK_SIGNING_KEY` in the ignored host `.env` file. The signing key
is an asymmetric Authentik certificate/key UUID.

Create the Authentik resources, recreate Gitea, then configure its persisted
authentication source:

```bash
scripts/authentik-apps.py --application gitea --apply
scripts/labctl.py service recreate dev/gitea
docker/dev/gitea/gitea-auth.py --host <host> --apply
```

Run the last command again after changing OIDC client settings. Keep the
registered callback URI exact:
`https://gitea.<domain>/user/oauth2/authentik/callback`.

## Verify

Confirm a `developers` member can sign in, a non-member is denied by Authentik,
an existing account links only through the intended flow, and local
administrator, Git SSH, and PAT workflows remain usable.

Gitea is a lightweight, open-source self-hosted Git service.
It's a community-managed fork of Gogs with enhanced features focused on Git management and CI/CD integration.

Installation:
The following commands will output a new SECRET_KEY and INTERNAL_TOKEN to stdout, which you can then place in your environment variables.
```
docker run -it --rm docker.gitea.com/gitea:1 gitea generate secret SECRET_KEY
docker run -it --rm docker.gitea.com/gitea:1 gitea generate secret INTERNAL_TOKEN
```
Do not lose/change your SECRET_KEY after the installation, otherwise the encrypted data can not be decrypted anymore.

Links:
- Home: https://about.gitea.com/
- Source: https://github.com/go-gitea/gitea
- Docs: https://docs.gitea.com/installation/install-with-docker

TODO: Generate SECRET_KEY and INTERNAL_TOKEN for enhanced security
TODO: Consider switching to PostgreSQL for improved performance with large repositories
