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

  local required_hostname="$1"
  assert_hostname "$required_hostname"

  # shellcheck disable=SC2034,SC2046
  DOCKER_DIR=$(dirname $(realpath "${BASH_SOURCE[0]}"))
  cd "${DOCKER_DIR}" || exit 1

  create_network_if_missing "proxy"
}

get_yaml_file() {
  local stack_dir="$1"
  local service_name="$2"
  echo "stacks/${stack_dir}/${service_name}.yaml"
}

get_env_file_args() {
  local service_name="$1"
  local env_files=()

  if [[ -f "${HOST_CONFIG_DIR}/../.env" ]]; then env_files+=("${HOST_CONFIG_DIR}/../.env"); fi  # Common .env file in config/docker
  if [[ -f "${HOST_CONFIG_DIR}/.env" ]];    then env_files+=("${HOST_CONFIG_DIR}/.env");    fi  # Host-specific .env file in config/docker/<hostname>

  if [[ -f "${HOST_CONFIG_DIR}/../.env.${service_name}" ]]; then env_files+=("${HOST_CONFIG_DIR}/../.env.${service_name}"); fi  # Common service-specific .env file in config/docker
  if [[ -f "${HOST_CONFIG_DIR}/.env.${service_name}" ]];    then env_files+=("${HOST_CONFIG_DIR}/.env.${service_name}");    fi  # Host- and service-specific .env file in config/docker/<hostname>

  local env_file_args=""
  for file in "${env_files[@]}"; do
    env_file_args+=" --env-file $file"
  done

  echo "$env_file_args"
}

docker_command() {
  local stack_dir="$1"
  local service_name="$2"
  local mode="$3"
  local yaml_file="$(get_yaml_file "${stack_dir}" "${service_name}")"
  local env_file_args="$(get_env_file_args "${service_name}")"

  case "$mode" in
    UPDATE|PULL)
      echo ">>> Pulling $stack_dir/$service_name"
      if grep -q "build:" "$yaml_file"; then
        # shellcheck disable=SC2086
        docker compose -f "$yaml_file" $env_file_args build --pull
      else
        # shellcheck disable=SC2086
        docker compose -f "$yaml_file" $env_file_args pull
      fi
      ;;&
  esac

  case "$mode" in
    UP|UPDATE)
      echo ">>> Starting $stack_dir/$service_name"
      # shellcheck disable=SC2086
      docker compose -f "$yaml_file" $env_file_args up --detach
      ;;&

    DOWN)
      echo ">>> Stopping $stack_dir/$service_name"
      # shellcheck disable=SC2086
      docker compose -f "$yaml_file" $env_file_args down
      ;;

    RESTART)
      echo ">>> Restarting $stack_dir/$service_name"
      # shellcheck disable=SC2086
      docker compose -f "$yaml_file" $env_file_args restart
      ;;

    RECREATE)
      echo ">>> Recreating $stack_dir/$service_name"
      # shellcheck disable=SC2086
      docker compose -f "$yaml_file" $env_file_args up --detach --force-recreate
      ;;
  esac
}

up() {
  # shellcheck disable=SC2153 # different than $mode
  case "$MODE" in
    UPDATE)
      docker_command "$1" "$2" "UPDATE";;
    PULL)
      docker_command "$1" "$2" "PULL";;
    *)
      docker_command "$1" "$2" "UP";;
  esac
}

down() {
  docker_command "$1" "$2" "DOWN"
}

restart() {
  docker_command "$1" "$2" "RESTART"
}

recreate() {
  docker_command "$1" "$2" "RECREATE"
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
