# Open WebUI Authentik OIDC

Open WebUI uses native OIDC for Authentik's `users` group. It redirects to
Authentik by default while retaining password authentication for recovery; use
`?form=1` on the login page to access the local form.

## Setup

Create `config/docker/<host>/open-webui/authentik-client-secret` with mode
`0600`. Set `OPEN_WEBUI_AUTHENTIK_CLIENT_ID`,
`OPEN_WEBUI_AUTHENTIK_CLIENT_SECRET`, and `OPEN_WEBUI_AUTHENTIK_SIGNING_KEY` in
ignored host configuration. The signing key is an asymmetric Authentik
certificate/key UUID used for ID-token validation.

```bash
scripts/authentik-apps.py --application open-webui --apply
scripts/labctl.py service recreate ai/open-webui
```

Keep the callback URI exact:
`https://open-webui.<domain>/oauth/oidc/callback`. Account merging by email
requires Authentik to provide verified, unique email addresses.

## Verify

Confirm an authorized user can sign in, a user outside `users` is denied, an
existing account links as intended, and local-password recovery still works.
