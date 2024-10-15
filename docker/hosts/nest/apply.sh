#!/usr/bin/env bash
set -e

cd "$(dirname "$0")" || exit
# shellcheck disable=SC1091
. ../../common.sh

assert_hostname "nest"
init

set +e

# Security -> TODO core
up security crowdsec
up security traefik
up security authelia
up security wg-easy
up security cloudflared
up security endlessh

# Dashboard
up dashboard homepage

# Infra
up infra portainer
up infra adguardhome
up infra unifi-controller
up infra ddclient

# Monitoring
up monitoring scrutiny
up monitoring uptime-kuma
up monitoring prometheus
up monitoring grafana

# Automation
up automation homeassistant
up automation n8n
# down automation olivetin

# Media
up media/video jellyfin # NAS
up media/video jellyfin-vue # NAS
up media/video metube # NAS
up media/audio navidrome # NAS
up media/ebook calibre # NAS
up media/ebook calibre-web # NAS
up media/ebook kiwix-serve

# Storage
up storage syncthing # NAS
up storage filebrowser
down storage minio
up storage webdav
up storage bees

# Backup
down backup kopia-nas # NAS
up backup kopia-b2 # NAS

# Dev
up dev code-server
down dev gitlab
down dev jupyter-notebook

# Tools
up tools homelab-docs
up tools vaultwarden
up tools openspeedtest
up tools cyberchef
up tools guacamole

# AI
up ai ollama
up ai litellm
up ai autogenstudio
up ai sillytavern

# Communication
# down communication matrix-synapse

# Arr
up arr radarr
up arr sonarr
up arr bazarr
up arr readarr
up arr prowlarr
up arr jellyseerr
up arr flaresolverr

# Game
# down game legendary-minecraft

# Personal
up personal personal-web

cleanup
