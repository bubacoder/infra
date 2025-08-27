#!/usr/bin/env python3
"""
Docker services management script.
Uses YAML configuration to manage Docker services.
"""

import argparse
import logging
import os
import socket
import subprocess
import sys
from pathlib import Path

import yaml

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Global variables
docker_stacks_dir: Path = Path(__file__).parent.absolute()


def create_network_if_missing(network_name: str) -> None:
    """Create Docker network if it doesn't exist."""
    try:
        docker(["network", "inspect", network_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        logger.info(f"Creating network: {network_name}")
        docker(["network", "create", "--driver", "bridge", network_name])


def create_localhost_link(docker_config_dir: Path) -> None:
    """Create 'localhost' symlink in the parent directory."""
    hostname = socket.gethostname()
    localhost_link = docker_config_dir / "localhost"
    hostname_dir = docker_config_dir / hostname

    if hostname_dir.exists() and hostname_dir.is_dir():
        # Create or update the localhost symlink
        if localhost_link.exists():
            if localhost_link.is_symlink():
                localhost_link.unlink()
            else:
                logger.error(f"Error: {localhost_link} exists but is not a symlink. Cannot create link.")
                return

        try:
            os.symlink(f"{hostname}/", localhost_link, target_is_directory=True)
        except Exception as e:
            logger.error(f"Error creating localhost symlink: {e}")


def get_compose_file(stack_dir: Path, service_name: str) -> Path:
    """Get the yaml file path for a service."""
    return stack_dir / f"{service_name}.yaml"


def has_build_directive(compose_file: Path) -> bool:
    """Check if the service uses a build directive."""
    with open(compose_file) as f:
        yaml_content = yaml.safe_load(f)
        if yaml_content and 'services' in yaml_content:
            for service_config in yaml_content['services'].values():
                if 'build' in service_config:
                    return True
    return False


def get_env_file_args(host_config_dir: Path, service_name: str) -> list[str]:
    """Get environment file arguments for Docker Compose with normalized paths."""
    env_paths = [
        host_config_dir.parent / ".env",                  # Common .env file in config/docker
        host_config_dir / ".env",                         # Host-specific .env file in config/docker/<hostname>
        host_config_dir.parent / f".env.{service_name}",  # Common service-specific .env file in config/docker
        host_config_dir / f".env.{service_name}"          # Host- and service-specific .env file in config/docker/<hostname>
    ]

    args = []
    for file in env_paths:
        absolute_path = file.resolve()
        if absolute_path.is_file():
            args.extend(["--env-file", str(absolute_path)])
    return args


def docker(cmd: list[str], env=None, stdin=None, stdout=None, stderr=None) -> None:
    subprocess.run(["docker"] + cmd, env=env, stdin=stdin, stdout=stdout, stderr=stderr, check=True)


def docker_command(host_config_dir: Path, stack_dir: Path, service_name: str, action: str) -> None:
    """Execute Docker Compose command for a service."""
    print()  # empty line for separation

    compose_file = get_compose_file(stack_dir, service_name)
    if not compose_file.exists():
        logger.error(f"Compose file not found: {compose_file}")
        return

    env_file_args = get_env_file_args(host_config_dir, service_name)

    # Handle pull operations
    if action in ["update", "pull"]:
        logger.info(f">>> Pulling {stack_dir}/{service_name}")

        if has_build_directive(compose_file):
            # Bake: https://docs.docker.com/guides/compose-bake/
            env = os.environ.copy()
            env["COMPOSE_BAKE"] = "true"
            docker(["compose", "-f", compose_file, *env_file_args, "build", "--pull"], env=env)
        else:
            docker(["compose", "-f", compose_file, *env_file_args, "pull"])

    # Handle other operations
    match action:
        case "up" | "update":
            logger.info(f">>> Starting {stack_dir}/{service_name}")
            docker(["compose", "-f", compose_file, *env_file_args, "up", "--detach"])

        case "down":
            logger.info(f">>> Stopping {stack_dir}/{service_name}")
            docker(["compose", "-f", compose_file, *env_file_args, "down"])

        case "restart":
            logger.info(f">>> Restarting {stack_dir}/{service_name}")
            docker(["compose", "-f", compose_file, *env_file_args, "restart"])

        case "recreate":
            logger.info(f">>> Recreating {stack_dir}/{service_name}")
            docker(["compose", "-f", compose_file, *env_file_args, "up", "--detach", "--force-recreate"])


def load_services_config(config_file: str) -> dict:
    """Load services configuration from YAML file."""
    try:
        with open(config_file) as file:
            config = yaml.safe_load(file)
            return config
    except Exception as e:
        logger.error(f"Error loading configuration file {config_file}: {e}")
        sys.exit(1)


def process_services(host_config_dir: Path, config: dict, state_override: str | None = None) -> None:
    """Process services based on the configuration."""
    if not config or 'services' not in config:
        logger.error("Error: Invalid configuration format. 'services' key not found.")
        return

    services = config['services']

    # Process services using the new structure
    for category_entry in services:
        # Each entry should have a single key (the category name) and a list of services
        if not category_entry or len(category_entry) != 1:
            logger.warning(f"Skipping invalid category entry: {category_entry}")
            continue

        category = list(category_entry.keys())[0]
        service_list = category_entry[category]

        # Process each service in this category
        for service in service_list:
            name = service.get('name', '')
            if not name:
                logger.warning(f"Skipping invalid service entry in category {category}: missing name")
                continue

            state = state_override or service.get('state', 'up')
            if state not in ('up', 'update', 'pull', 'down', 'restart', 'recreate'):
                logger.warning(f"Unknown state '{state}' for service {category}/{name}")
                continue

            docker_command(host_config_dir, docker_stacks_dir / category, name, state)


def get_host_config_dir() -> Path:
    hostname = socket.gethostname().lower()
    script_dir = Path(__file__).parent.absolute()
    docker_config_dir = script_dir.parent / "config" / "docker"
    return docker_config_dir / hostname


def cmd_config_apply(args) -> None:
    """Apply configuration to Docker services."""
    if args.config:
        config_file = args.config
        host_config_dir = Path(config_file).parent
    else:
        # Use the default location based on hostname
        host_config_dir = get_host_config_dir()
        config_file = host_config_dir / "services.yaml"

    logger.info("Init...")
    config = load_services_config(config_file)
    create_localhost_link(host_config_dir.parent)
    create_network_if_missing("proxy")

    # Process services with optional mode override
    process_services(host_config_dir, config, args.mode)

    # Cleanup old images if enabled in config and in update mode
    if args.mode == 'update':
        logger.info("Cleanup...")
        # Remove unused and dangling images created before given timestamp (21 days)
        docker(["image", "prune", "--all", "--force", "--filter", "until=504h"])


def cmd_service(args) -> None:
    """Manage individual Docker services."""
    if not args.name:
        logger.error("Service name is required")
        sys.exit(1)

    # Parse service name in format category/subcategory/name
    name_parts = args.name.split('/')
    if len(name_parts) < 2:
        logger.error("Service name must be in format category/name or category/subcategory/name")
        sys.exit(1)

    # The last part is always the service name
    service_name = name_parts[-1]
    # Everything before the last part is the category path
    category_path = '/'.join(name_parts[:-1])

    docker_command(get_host_config_dir(), docker_stacks_dir / category_path, service_name, args.operation)


def main() -> None:
    parser = argparse.ArgumentParser(description='Manage Docker services using YAML configuration.')
    subparsers = parser.add_subparsers(dest='command', help='Commands', required=True)

    # Config command
    config_parser = subparsers.add_parser('config', help='Manage service configurations')
    config_subparsers = config_parser.add_subparsers(dest='config_command', help='Config subcommands', required=True)

    # Config apply command
    config_apply_parser = config_subparsers.add_parser('apply', help='Apply service configurations')
    config_apply_parser.add_argument('--config', '-c', help='Path to the YAML configuration file')
    config_apply_parser.add_argument('--mode', '-m', help='Override state for all services (up, down, restart, recreate, update, pull)')

    # Service command
    service_parser = subparsers.add_parser('service', help='Manage individual services')
    service_parser.add_argument('operation', choices=['up', 'down', 'restart', 'recreate', 'update', 'pull'], help='Operation to perform on the service')
    service_parser.add_argument('name', help='Service name in format category/name or category/subcategory/name')

    args = parser.parse_args()

    # Handle command structure
    if args.command == 'config':
        if args.config_command == 'apply':
            cmd_config_apply(args)
    elif args.command == 'service':
        cmd_service(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
