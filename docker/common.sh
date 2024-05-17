# shellcheck disable=SC2148

create_network_if_missing() {
  local network_name="$1"
  if ! docker network inspect "$network_name" &>/dev/null; then
    docker network create --driver bridge "$network_name"
  fi
}

init() {
  echo "Init..."
  create_network_if_missing "proxy"
}

up() {
  local stack_dir="$1"
  local service_name="$2"
  local yaml_file="../../stacks/$stack_dir/$service_name.yaml"

  echo ">>> Starting $stack_dir/$service_name"

  if [[ "${UPDATE:-false}" == "true" ]]; then
    if grep -q "build:" "$yaml_file"; then
      docker compose -f "$yaml_file" build --pull
    else
      docker compose -f "$yaml_file" --env-file .env pull
    fi
  fi

  docker compose -f "$yaml_file" --env-file .env up --detach
}

down() {
  local stack_dir="$1"
  local service_name="$2"
  local yaml_file="../../stacks/$stack_dir/$service_name.yaml"

  echo ">>> Stopping $stack_dir/$service_name"
  docker compose -f "$yaml_file" --env-file .env down
}

restart() {
  local stack_dir="$1"
  local service_name="$2"
  down "$stack_dir" "$service_name"
  up "$stack_dir" "$service_name"
}

cleanup() {
  if [[ "${UPDATE:-false}" == "true" ]]; then
    echo "Cleanup..."
    # Remove unused and dangling images created before given timestamp
    docker image prune --all --force --filter "until=21d"
  fi
}

assert_hostname() {
  local required_hostname="$1"
  local current_hostname
  current_hostname=$(hostname)

  if [[ "$current_hostname" != "$required_hostname" ]]; then
    echo "Error: Current hostname ($current_hostname) does not match the required hostname ($required_hostname). Exiting..."
    exit 1
  fi
}
