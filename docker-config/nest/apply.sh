#!/bin/bash

. ../common.sh

up infra portainer
up infra adguardhome
up infra unifi-controller
up infra uptime-kuma
#up infra wireguard
#up infra nginx-proxy-manager

up homeaut homeassistant

up dashboard hemidall

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
#up media immich
#up media plex

#up storage samba
up storage code-server
up storage syncthing
#up storage google-drive
up storage filebrowser
#up storage kopia
up storage scrutiny