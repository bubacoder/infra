#!/usr/bin/env bash
set -e


### Common code ###

# shellcheck disable=SC2034,SC2046
HOST_CONFIG_DIR=$(dirname $(realpath -s "$0"))

# Create 'localhost' link
(cd "$HOST_CONFIG_DIR/.." && ln -sf "$(hostname)/" "localhost")

# If the config dir is within the infra repo
DOCKER_STACKS_DIR=${HOST_CONFIG_DIR}/../../../docker/

if [ ! -d "$DOCKER_STACKS_DIR" ]; then
  # If the config dir is a separate repo
  DOCKER_STACKS_DIR=${HOST_CONFIG_DIR}/../../../infra/docker/
fi

# shellcheck disable=SC1091
source "${DOCKER_STACKS_DIR}/common.sh"


### Host-specific configuration ###

init "myhost"

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
up storage couchdb

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
up tools kasm
up tools stirling-pdf
up tools searxng

# AI
up ai ollama
up ai litellm
up ai open-webui
up ai open-webui-pipelines
up ai autogenstudio
up ai sillytavern
up ai qdrant

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


### Common code ###

cleanup
