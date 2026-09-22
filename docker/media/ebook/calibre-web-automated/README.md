# Calibre-Web-Automated Authentik OIDC

Calibre-Web-Automated uses native OIDC for Authentik's `media` group. Keep its
local administrator and reader credentials: OPDS, Kobo, KOReader, and other
non-browser clients do not use browser OIDC.

## Setup

Create `config/docker/<host>/calibre-web-automated/authentik-client-secret`
with mode `0600`, set `CALIBRE_WEB_AUTOMATED_AUTHENTIK_CLIENT_ID` in ignored
`config/docker/<host>/.env.calibre-web-automated`, then create the Authentik
application:

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

Calibre-Web Automated (formerly Calibre-Web Automator) combines the modern lightweight Calibre-Web UI with the robust feature set of Calibre, plus a slew of extra automations.
It provides automatic ingest, conversion, metadata fetch, cover/metadata enforcement, EPUB fixing, duplicate detection, KOReader syncing (KOSync), enhanced OAuth 2.0/OIDC authentication and more.

Default login: `admin` / `admin123`

Links:
- Home: https://github.com/crocodilestick/Calibre-Web-Automated
- Source: https://github.com/crocodilestick/Calibre-Web-Automated
- Docs: https://github.com/crocodilestick/Calibre-Web-Automated/wiki
- Compose example: https://github.com/crocodilestick/Calibre-Web-Automated/blob/main/docker-compose.yml

TODO: Change the default admin credentials after first login and enable Uploads under
  Settings -> Basic Configuration -> Feature Configuration.
TODO: Configure CWA-specific behaviour in the CWA Settings panel (target format, ignored / auto-converted formats).
TODO: Consider migrating/replacing the existing calibre-web service to avoid two services managing the same library.
TODO: Optional: set HARDCOVER_TOKEN for the Hardcover metadata provider (https://docs.hardcover.app/api/getting-started/).
TODO: Optional: bind a Calibre plugins folder to /config/.config/calibre/plugins and copy customize.py.json into it.
