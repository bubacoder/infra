#!/bin/bash

up()
{
    echo ">>> Starting $1/$2"
    #docker compose -f $1/$2.yaml --env-file variables pull
    docker compose -f $1/$2.yaml --env-file variables up --detach
}

down()
{
    echo ">>> Stopping $1/$2"
    docker compose -f $1/$2.yaml --env-file variables down
}
