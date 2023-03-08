#!/bin/bash

. ../common.sh

# docker network create proxy

up infra traefik
up infra authelia
up infra portainer
up infra adguardhome
up infra uptime-kuma
up infra unifi-controller
up infra wg-easy

up dashboard hemidall
up dashboard homepage

up smarthome homeassistant

up arr radarr
up arr sonarr
up arr bazarr
up arr prowlarr
up arr jellyseerr
up arr flaresolverr
#up arr jackett

up fileshare transmission
#up fileshare sabnzbd

up media jellyfin
up media metube
#up media immich
#up media plex

#up storage samba
up storage syncthing
#up storage google-drive
up storage filebrowser
up storage kopia
up storage kopia-b2
up storage scrutiny

up tools code-server
up tools vaultwarden
up tools openspeedtest
up tools cyberchef
