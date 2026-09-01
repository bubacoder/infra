# qBittorrent Authentik ForwardAuth

Authentik ForwardAuth protects the browser UI for Authentik's `media` group.
qBittorrent WebUI authentication remains necessary for API clients and any
direct UI route; BitTorrent peer ports are separate protocol exposure.

## Setup

```bash
scripts/authentik-apps.py --application qbittorrent --apply
scripts/labctl.py service recreate fileshare/qbittorrent
```

For proxy-only browser access, enable qBittorrent's whitelist bypass only for
Traefik's exact proxy-network `/32`; never whitelist the entire proxy network.
Reserve Traefik's IP or update that whitelist after Traefik recreation. Keep
WebUI port 8080 unpublished on the host.

## Verify

Confirm a `media` member reaches the WebUI, a non-member is denied, direct UI
access still needs native authentication, and API clients plus peer traffic
continue to work.
