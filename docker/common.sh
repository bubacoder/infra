# shellcheck disable=SC2148
# Commmon functions used by apply*.sh

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

get_yaml_file() {
  local stack_dir="$1"
  local service_name="$2"
  echo "../../stacks/${stack_dir}/${service_name}.yaml"
}

get_env_file_args() {
  local service_name="$1"
  local env_files=()

  if [[ -f "../.env" ]]; then env_files+=("../.env"); fi  # Common .env file in docker/hosts
  if [[ -f ".env" ]];    then env_files+=(".env");    fi  # Host-specific .env file in docker/hosts/<hostname>

  if [[ -f "../.env.${service_name}" ]]; then env_files+=("../.env.${service_name}"); fi  # Common service-specific .env file in docker/hosts
  if [[ -f ".env.${service_name}" ]];    then env_files+=(".env.${service_name}");    fi  # Host- and service-specific .env file in docker/hosts/<hostname>

  local env_file_args=""
  for file in "${env_files[@]}"; do
    env_file_args+=" --env-file $file"
  done

  echo "$env_file_args"
}

up() {
  local stack_dir="$1"
  local service_name="$2"
  local yaml_file="$(get_yaml_file "${stack_dir}" "${service_name}")"
  local env_file_args="$(get_env_file_args "${service_name}")"

  echo ">>> Starting $stack_dir/$service_name"

  if [[ "${UPDATE:-false}" == "true" ]]; then
    if grep -q "build:" "$yaml_file"; then
      # shellcheck disable=SC2086
      docker compose -f "$yaml_file" $env_file_args build --pull
    else
      # shellcheck disable=SC2086
      docker compose -f "$yaml_file" $env_file_args pull
    fi
  fi

  # shellcheck disable=SC2086
  docker compose -f "$yaml_file" $env_file_args up --detach
}

down() {
  local stack_dir="$1"
  local service_name="$2"
  local yaml_file="$(get_yaml_file "${stack_dir}" "${service_name}")"
  local env_file_args="$(get_env_file_args "${service_name}")"

  echo ">>> Stopping $stack_dir/$service_name"
  # shellcheck disable=SC2086
  docker compose -f "$yaml_file" $env_file_args down
}

restart() {
  local stack_dir="$1"
  local service_name="$2"
  local yaml_file="$(get_yaml_file "${stack_dir}" "${service_name}")"
  local env_file_args="$(get_env_file_args "${service_name}")"

  echo ">>> Restarting $stack_dir/$service_name"
  # shellcheck disable=SC2086
  docker compose -f "$yaml_file" $env_file_args restart
}

recreate() {
  local stack_dir="$1"
  local service_name="$2"
  local yaml_file="$(get_yaml_file "${stack_dir}" "${service_name}")"
  local env_file_args="$(get_env_file_args "${service_name}")"

  echo ">>> Recreating $stack_dir/$service_name"
  # shellcheck disable=SC2086
  docker compose -f "$yaml_file" $env_file_args up --detach --force-recreate
}

cleanup() {
  if [[ "${UPDATE:-false}" == "true" ]]; then
    echo "Cleanup..."
    # Remove unused and dangling images created before given timestamp (21 days)
    docker image prune --all --force --filter "until=504h"
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
