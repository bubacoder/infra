#!/bin/bash
set -euo pipefail

echo Mounting storage...

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

create_dir /storage/
mount_storage

create_dir /storage/torrent-downloads
create_dir /storage/torrent-watch
create_dir /storage/media/tvseries
create_dir /storage/media/movies
create_dir /storage/media/audio
