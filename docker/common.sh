#!/bin/bash

init()
{
    echo Init...
}

up()
{
    echo ">>> Starting $1/$2"
    if ${PULL:-false}; then
        docker compose -f "$1/$2.yaml" --env-file .env pull
    fi
    docker compose -f "$1/$2.yaml" --env-file .env up --detach
}

down()
{
    echo ">>> Stopping $1/$2"
    docker compose -f "$1/$2.yaml" --env-file .env down
}

cleanup()
{
    if ${PULL:-false}; then
        echo Cleanup...
        docker image prune -a -f
    fi
}

assert-hostname() {
  requiredHostname="$1"
  currentHostname=$(hostname)

  if [ "$currentHostname" != "$requiredHostname" ]; then
    echo "Error: Current hostname ($currentHostname) does not match the required hostname ($requiredHostname). Exiting..."
    exit 1
  fi
}
