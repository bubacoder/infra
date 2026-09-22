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

The qBittorrent project aims to provide an open-source software alternative to µTorrent. qBittorrent is based on the Qt toolkit and libtorrent-rasterbar library.
The default username/password is printed to the terminal on container start.

Recommended setup steps:
- Keep qBittorrent WebUI authentication enabled for API clients. Authentik
  protects browser access through Traefik.
  - For the proxy-only setup below, enable "Bypass authentication for clients
    on whitelisted IP subnets", whitelist Traefik's proxy-network IP as a
    /32, and leave "Reverse proxy support" disabled. qBittorrent then bypasses
    its login only for Traefik, rather than for every client or container on
    the proxy network.
  - Traefik's IP can change when it is recreated. Use a dedicated network with
    a reserved Traefik IP for a durable configuration, or update the /32
    whitelist after each Traefik recreation. Do not whitelist the full proxy
    network.
  - Direct host exposure (see "separate host" note below) must retain WebUI
    authentication because the browser connects to qBittorrent directly.
- The image is build locally (see: `Dockerfile`) and includes the VueTorrent (https://github.com/WDaan/VueTorrent) web interface. To enable it, point your alternate WebUI location to '/usr/vuetorrent' folder in qBittorrent settings.
- Configure categories (Settings menu) to specify default download locations
- Setup forwarding of port 6881 (TCP, UDP) in the router, check open port: https://www.yougetsignal.com/tools/open-ports/

Links:
- Home: https://www.qbittorrent.org/
- Image: https://hub.docker.com/r/linuxserver/qbittorrent
