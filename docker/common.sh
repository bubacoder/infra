# shellcheck disable=SC2148

init()
{
  echo Init...
}

up()
{
  echo ">>> Starting $1/$2"
  yaml="../../stacks/$1/$2.yaml"
  if ${UPDATE:-false}; then
    if grep -q "build:" "$yaml"; then
      docker compose -f "$yaml" build --pull
    else
      docker compose -f "$yaml" --env-file .env pull
    fi
  fi
  docker compose -f "$yaml" --env-file .env up --detach
}

down()
{
  echo ">>> Stopping $1/$2"
  yaml="../../stacks/$1/$2.yaml"
  docker compose -f "$yaml" --env-file .env down
}

restart()
{
  down "$1" "$2"
  up "$1" "$2"
}

cleanup()
{
  if ${UPDATE:-false}; then
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
