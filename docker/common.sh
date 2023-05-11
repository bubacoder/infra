#!/bin/bash

up()
{
    echo ">>> Starting $1/$2"
    #docker compose -f $1/$2.yaml --env-file .env pull
    docker compose -f $1/$2.yaml --env-file .env up --detach
}

down()
{
    echo ">>> Stopping $1/$2"
    docker compose -f $1/$2.yaml --env-file .env down
}
