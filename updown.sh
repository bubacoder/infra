#!/bin/bash

up()
{
    docker compose -f $1.yaml --env-file ../.env up --detach
}

down()
{
    docker compose -f $1.yaml down
}


OIFS=$IFS
IFS=' '

YAMLS=$(find . -type f -name "*.yaml")
UP=$(echo $YAMLS | grep -v .down.)
DOWN=$(echo $YAMLS | grep .down.)

#echo $UP
#echo $DOWN

IFS=$OIFS

for SERVICE in $DOWN
do
    echo "Bringing ${SERVICE} DOWN"
done

for SERVICE in $UP
do
    echo "Bringing ${SERVICE} UP"
done

