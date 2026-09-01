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
