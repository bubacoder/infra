# Open WebUI Authentik OIDC

Open WebUI uses native OIDC for Authentik's `users` group. It redirects to
Authentik by default while retaining password authentication for recovery; use
`?form=1` on the login page to access the local form.

## Setup

Create `config/docker/<host>/open-webui/authentik-client-secret` with mode
`0600`. Set `OPEN_WEBUI_AUTHENTIK_CLIENT_ID`,
`OPEN_WEBUI_AUTHENTIK_CLIENT_SECRET` in ignored
`config/docker/<host>/.env.open-webui`, and set
`OPEN_WEBUI_AUTHENTIK_SIGNING_KEY` in the ignored host `.env`. The signing key
is an asymmetric Authentik certificate/key UUID used for ID-token validation.

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

Open WebUI is an extensible, feature-rich, and user-friendly self-hosted WebUI for various LLM runners, supported LLM runners include Ollama and OpenAI-compatible APIs.

Links:
- Home: https://openwebui.com/
- Source: https://github.com/open-webui/open-webui/
- https://docs.openwebui.com/getting-started/

Compose file based on: https://github.com/open-webui/open-webui/blob/main/docker-compose.yaml
