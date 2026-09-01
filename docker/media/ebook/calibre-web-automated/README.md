# Calibre-Web-Automated Authentik OIDC

Calibre-Web-Automated uses native OIDC for Authentik's `media` group. Keep its
local administrator and reader credentials: OPDS, Kobo, KOReader, and other
non-browser clients do not use browser OIDC.

## Setup

Create `config/docker/<host>/calibre-web-automated/authentik-client-secret`
with mode `0600`, set `CALIBRE_WEB_AUTOMATED_AUTHENTIK_CLIENT_ID` in ignored
host configuration, then create the Authentik application:

```bash
scripts/authentik-apps.py --application calibre-web-automated --apply
```

In the CWA administrative UI, configure generic OAuth/OIDC with issuer
`https://sso.<domain>/application/o/calibre-web-automated/`, the configured
client ID and secret, and scopes `openid profile email`. Keep the callback URI
exact: `https://calibre-web-automated.<domain>/login/generic/authorized`.
`TRUSTED_PROXY_COUNT: 1` is required so CWA generates HTTPS callbacks behind
Traefik. Leave OAuth role synchronization disabled unless its group mapping has
been deliberately designed.

## Verify

Confirm a `media` member can sign in, a non-member is denied, an existing local
account links correctly, and local recovery plus OPDS and reader clients remain
usable.
