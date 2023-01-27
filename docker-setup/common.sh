
up()
{
    docker compose -f $1.yaml --env-file ../.env.$(hostname) up --detach
}

down()
{
    docker compose -f $1.yaml --env-file ../.env.$(hostname) down
}


