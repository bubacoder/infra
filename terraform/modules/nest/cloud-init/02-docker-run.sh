#!/bin/bash

# Location: /var/lib/cloud/instance/scripts

echo Starting Docker containers...

function mount_storage {
    max_attempts=60
    counter=0
    success=0

    while [ "$success" -eq 0 ] && [ "$counter" -lt $max_attempts ]
    do
        if [ -b "/dev/sdc1" ]
        then
            success=1
        else
            sleep 1
            ((counter++))
        fi
    done

    if [ "$success" -eq 0 ]
    then
        echo "Error: /dev/sdc1 not available after $max_attempts attempts."
        exit
    else
        echo "/dev/sdc1 is now available."
        mount /dev/sdc1 /storage
    fi
}

function create_dir {
    if [ ! -d "$1" ]; then
        mkdir --parents "$1"
    fi
}

function wait_until_installed {
    while ! command -v "$1" >/dev/null 2>&1; do
        sleep 1
    done
    echo "Docker has been installed"
}


# Mount
create_dir /storage/
mount_storage
create_dir "${CONTAINERDATA}/"


# Start containers
wait_until_installed "docker"

docker compose -f portainer.yaml up --detach

docker compose -f syncthing.yaml up --detach

create_dir /storage/torrent-downloads
create_dir /storage/torrent-watch
docker compose -f transmission.yaml up --detach

create_dir /storage/media/tvseries
create_dir /storage/media/movies
create_dir /storage/media/audio
docker compose -f jellyfin.yaml up --detach

docker compose -f filebrowser.yaml up --detach

#docker compose -f homeassistant.yaml up --detach
#docker compose -f unifi-controller.yaml up --detach

