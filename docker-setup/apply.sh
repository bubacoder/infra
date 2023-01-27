#!/bin/bash

ENV=$(hostname)

up()
{
    echo ">>> Starting $1/$2"
    docker compose -f $1/$2.yaml --env-file ".env.$ENV" pull
    docker compose -f $1/$2.yaml --env-file ".env.$ENV" up --detach
}

down()
{
    echo ">>> Stopping $1/$2"
    docker compose -f $1/$2.yaml --env-file ".env.$ENV" down
}


up infra portainer
up infra adguardhome
down infra wireguard
down infra unifi-controller
down infra nginx-proxy-manager

down homeaut homeassistant

up dashboard hemidall

down arr radarr
down arr sonarr
down arr jellyseerr
down arr bazarr
down arr jackett
down arr prowlarr

down fileshare sabnzbd
up fileshare transmission

down media jellyfin
down media immich
down media plex

up storage samba
down storage code-server
down storage syncthing
down storage google-drive
down storage filebrowser
