#!/bin/bash

# shellcheck disable=SC1091
. ../common.sh

assert-hostname "nest"
init

# docker network create proxy

up security traefik
up security authelia
up security wg-easy
up security cloudflared

up dashboard homepage

up infra portainer
up infra adguardhome
up infra unifi-controller

up monitoring scrutiny
up monitoring uptime-kuma
up monitoring prometheus
up monitoring grafana

up smarthome homeassistant

up media jellyfin
up media jellyfin-vue
up media metube
#up media immich
up media photoprism

#down storage samba
up storage syncthing
#up storage google-drive
up storage filebrowser
up storage kopia-nas
up storage kopia-b2

up dev code-server
up dev gitlab
up dev jupyter-notebook

up tools vaultwarden
up tools openspeedtest
up tools cyberchef
up tools guacamole

up arr radarr
up arr sonarr
up arr bazarr
up arr prowlarr
up arr jellyseerr
up arr flaresolverr

down game legendary-minecraft

cleanup
