#!/bin/bash

DOCKER_VOLUMES=/srv/docker-volumes

stop-all-containers()
{
    docker ps -q | xargs docker stop
}

start-selected-containers()
{
    ./apply-local.sh
}

kopia-backup-docker-volumes()
{
    docker exec -it kopia-nas /usr/bin/kopia --config-file=/app/config/repository.config snapshot create /sources/nest/docker-volumes
}

tar-backup-docker-volumes()
{
    tar c -v --bzip2 -f ~/docker-volumes-"$(date +'%Y-%m-%d')".tar.bz2 $DOCKER_VOLUMES
}

stop-all-containers
#kopia-backup-docker-volumes
tar-backup-docker-volumes
start-selected-containers
