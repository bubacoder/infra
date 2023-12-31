#!/bin/bash

# shellcheck disable=SC1091
. ../../common.sh

assert-hostname "nest"
init

# docker network create proxy

up security crowdsec
up security traefik
up security authelia
up security wg-easy
up security cloudflared
up security endlessh

up dashboard homepage

up infra portainer
up infra adguardhome
up infra unifi-controller

up monitoring scrutiny # down -> clients
up monitoring uptime-kuma
up monitoring prometheus
up monitoring grafana

up smarthome homeassistant

# Media

up media/video jellyfin
up media/video jellyfin-vue
up media/video metube

up media/audio navidrome

up media/ebook calibre
up media/ebook calibre-web
down media/photo photoprism

up storage syncthing
up storage filebrowser

up backup kopia-nas
up backup kopia-b2

up dev code-server
down dev gitlab
down dev jupyter-notebook

up tools vaultwarden
up tools openspeedtest
up tools cyberchef
up tools guacamole

down tools olivetin # wip
down personal misikoli-web # wip

up arr radarr
up arr sonarr
up arr bazarr
up arr readarr
up arr prowlarr
up arr jellyseerr
up arr flaresolverr

down game legendary-minecraft

cleanup
