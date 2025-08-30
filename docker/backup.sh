#!/usr/bin/env bash
set -euo pipefail

DOCKER_VOLUMES="/srv/docker-volumes" # TODO configure
BACKUP_FILE="docker-volumes-$(date +'%Y-%m-%d').tar.bz2"
BACKUP_PATH="$HOME/$BACKUP_FILE"

stop_all_containers() {
  # shellcheck disable=SC2046
  docker stop $(docker ps -q)
}

start_selected_containers() {
  task docker:apply
}

kopia_backup_docker_volumes() {
  docker exec -it kopia-nas /usr/bin/kopia --config-file=/app/config/repository.config snapshot create /sources/nest/docker-volumes
}

compress_docker_volumes() {
  tar -cvf "$BACKUP_PATH" --bzip2 "$DOCKER_VOLUMES"
}

stop_all_containers
#kopia_backup_docker_volumes
compress_docker_volumes
start_selected_containers
