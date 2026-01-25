#!/usr/bin/env python3
"""
Docker services management script.
Uses YAML configuration to manage Docker services.
"""

import argparse
import logging
import os
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@dataclass
class DockerOptions:
    """Configuration options for Docker operations."""
    pull_before_start: bool = False
    quiet: bool = False
    # Log options
    follow: bool = False
    tail: str = "all"
    since: str | None = None
    timestamps: bool = False


# Global variables
docker_stacks_dir: Path = (Path(__file__).resolve().parent.parent / "docker").resolve()
ALLOWED_STATES: tuple[str, ...] = ('pull', 'up', 'down', 'restart', 'recreate', 'config', 'logs')


def create_network_if_missing(network_name: str) -> None:
    """Create Docker network if it doesn't exist.

    Args:
        network_name: The name of the Docker network to check/create
    """
    try:
        docker(["network", "inspect", network_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        logger.info(f"Creating network: {network_name}")
        docker(["network", "create", "--driver", "bridge", network_name])


def get_external_networks(compose_file: Path) -> list[str]:
    """Extract external networks from a Docker Compose file."""
    networks: list[str] = []
    try:
        with open(compose_file) as f:
            yaml_content = yaml.safe_load(f) or {}
        networks_def = yaml_content.get("networks") or {}
        if isinstance(networks_def, dict):
            for key, cfg in networks_def.items():
                if not isinstance(cfg, dict):
                    continue
                ext = cfg.get("external", False)
                # Support: external: true | external: {name: "..."} | name: "..."
                name_override = cfg.get("name")
                if ext is True:
                    networks.append(name_override or key)
                elif isinstance(ext, dict):
                    networks.append(ext.get("name") or name_override or key)
    except (FileNotFoundError, yaml.YAMLError, OSError) as e:
        logger.warning(f"Error extracting networks from {compose_file}: {e}")

    return list(dict.fromkeys(networks))


def create_service_networks(compose_file: Path) -> None:
    """Create all external networks required by a service.

    Args:
        compose_file: Path to the Docker Compose file
    """
    networks = get_external_networks(compose_file)
    for network_name in networks:
        create_network_if_missing(network_name)


def create_localhost_link(docker_config_dir: Path) -> None:
    """Create 'localhost' symlink in the parent directory.

    Creates a symbolic link named 'localhost' that points to the current hostname directory.

    Args:
        docker_config_dir: The Docker configuration directory containing hostname subdirectories
    """
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
        except Exception:
            logger.exception("Error creating localhost symlink")


def get_compose_file(stack_dir: Path, service_name: str) -> Path:
    """Get the yaml file path for a service.

    Args:
        stack_dir: Directory containing service definitions
        service_name: Name of the service

    Returns:
        Path: The path to the service's compose file
    """
    return stack_dir / service_name / f"{service_name}.yaml"


def has_build_directive(compose_file: Path) -> bool:
    """Check if the service uses a build directive.

    Args:
        compose_file: Path to the Docker Compose file

    Returns:
        bool: True if the compose file contains any build directives
    """
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
    """Execute a docker command with the given arguments.

    Args:
        cmd: List of command arguments to pass to docker
        env: Environment variables for the subprocess
        stdin: Standard input for the subprocess
        stdout: Standard output for the subprocess
        stderr: Standard error for the subprocess
    """
    docker_bin = shutil.which("docker")
    if docker_bin is None:
        raise RuntimeError("Docker executable not found on PATH.") from None
    subprocess.run([docker_bin, *cmd], env=env, stdin=stdin, stdout=stdout, stderr=stderr, check=True)  # noqa: S603


def docker_pull(stack_dir: Path, service_name: str, compose_file: Path, env_file_args: list[str], quiet: bool = False) -> None:
    """Pull Docker images for a service.

    Args:
        stack_dir: Directory containing the service definition
        service_name: Name of the service
        compose_file: Path to the Docker Compose file
        env_file_args: List of environment file arguments
        quiet: Whether to use quiet mode (default: False)
    """
    logger.info(f">>> Pulling {stack_dir}/{service_name}")
    if has_build_directive(compose_file):
        # Bake: https://docs.docker.com/guides/compose-bake/
        env = os.environ.copy()
        env["COMPOSE_BAKE"] = "true"
        build_cmd = ["compose", "-f", compose_file, *env_file_args, "build", "--pull"]
        if quiet:
            build_cmd.append("--quiet")
        docker(build_cmd, env=env)
    else:
        pull_cmd = ["compose", "-f", compose_file, *env_file_args, "pull"]
        if quiet:
            pull_cmd.append("--quiet")
        docker(pull_cmd)


def build_log_command_flags(options: DockerOptions) -> list[str]:
    """Build Docker Compose log command flags based on options.

    Args:
        options: Docker operation options containing log-specific settings

    Returns:
        list[str]: List of command flags for docker compose logs
    """
    flags = []
    if options.follow:
        flags.append("--follow")
    if options.tail and options.tail != "all":
        flags.extend(["--tail", options.tail])
    if options.since:
        flags.extend(["--since", options.since])
    if options.timestamps:
        flags.append("--timestamps")
    return flags


def docker_command(host_config_dir: Path, stack_dir: Path, service_name: str, action: str, options: DockerOptions = None) -> None:
    """Execute Docker Compose command for a service.

    Args:
        host_config_dir: Path to the host-specific configuration directory
        stack_dir: Path to the service category directory
        service_name: Name of the service to operate on
        action: The action to perform (pull, up, down, restart, recreate, config, logs)
        options: Docker operation options (default: None)
    """
    if options is None:
        options = DockerOptions()
    logger.info("")  # separation

    compose_file = get_compose_file(stack_dir, service_name)
    if not compose_file.exists():
        logger.error(f"Compose file not found: {compose_file}")
        return

    # Ensure external networks exist only when (re)starting containers
    if action in {"up", "recreate"}:
        create_service_networks(compose_file)

    env_file_args = get_env_file_args(host_config_dir, service_name)

    # Handle other operations
    match action:
        case "pull":
            docker_pull(stack_dir, service_name, compose_file, env_file_args, options.quiet)

        case "up":
            if options.pull_before_start:
                docker_pull(stack_dir, service_name, compose_file, env_file_args, options.quiet)

            logger.info(f">>> Starting {stack_dir}/{service_name}")
            docker(["compose", "-f", compose_file, *env_file_args, "up", "--detach"])

        case "down":
            logger.info(f">>> Stopping {stack_dir}/{service_name}")
            docker(["compose", "-f", compose_file, *env_file_args, "down"])

        case "restart":
            logger.info(f">>> Restarting {stack_dir}/{service_name}")
            docker(["compose", "-f", compose_file, *env_file_args, "restart"])

        case "recreate":
            if options.pull_before_start:
                docker_pull(stack_dir, service_name, compose_file, env_file_args, options.quiet)

            logger.info(f">>> Recreating {stack_dir}/{service_name}")
            docker(["compose", "-f", compose_file, *env_file_args, "up", "--detach", "--force-recreate"])

        case "config":
            logger.info(f">>> Checking {stack_dir}/{service_name}")
            docker(["compose", "-f", compose_file, *env_file_args, "config"])

        case "logs":
            logger.info(f">>> Showing logs for {stack_dir}/{service_name}")
            log_cmd = ["compose", "-f", compose_file, *env_file_args, "logs"]
            log_cmd.extend(build_log_command_flags(options))
            docker(log_cmd)


def load_services_config(config_file: str) -> dict:
    """Load services configuration from YAML file."""
    try:
        with open(config_file) as file:
            config = yaml.safe_load(file)
            return config
    except Exception:
        logger.exception(f"Error loading configuration file {config_file}")
        sys.exit(1)


def process_services(host_config_dir: Path, config: dict, state_override: str | None = None, pull_before_start: bool = False, quiet: bool = False) -> None:
    """Process services based on the configuration.

    Args:
        host_config_dir: Path to the host-specific configuration directory
        config: Dictionary containing service configurations
        state_override: State to override for all services (pull, up, down, etc.)
        pull_before_start: Whether to pull images before starting services
        quiet: Whether to use quiet mode for docker operations
    """
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

            state = (state_override or service.get('state', 'up')).lower()
            if state not in ALLOWED_STATES:
                logger.warning(f"Unknown state '{state}' for service {category}/{name}")
                continue

            docker_command(host_config_dir, docker_stacks_dir / category, name, state, DockerOptions(pull_before_start, quiet))


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

    # Process services with optional mode override
    process_services(host_config_dir, config, args.mode, args.pull_before_start, args.quiet)


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

    # Create options with all parameters
    options = DockerOptions(
        pull_before_start=args.pull_before_start,
        quiet=args.quiet
    )

    # Add log options if they exist in args and operation is 'logs'
    if args.operation == 'logs':
        if hasattr(args, 'follow'):
            options.follow = args.follow
        if hasattr(args, 'tail'):
            options.tail = args.tail
        if hasattr(args, 'since'):
            options.since = args.since
        if hasattr(args, 'timestamps'):
            options.timestamps = args.timestamps

    docker_command(get_host_config_dir(), docker_stacks_dir / category_path, service_name, args.operation, options)


def main() -> None:
    parser = argparse.ArgumentParser(description='Manage Docker services using YAML configuration.')
    subparsers = parser.add_subparsers(dest='command', help='Commands', required=True)

    # Config command
    config_parser = subparsers.add_parser('config', help='Manage service configurations')
    config_subparsers = config_parser.add_subparsers(dest='config_command', help='Config subcommands', required=True)

    # Config apply command
    config_apply_parser = config_subparsers.add_parser('apply', help='Apply service configurations')
    config_apply_parser.add_argument('--config', '-c', help='Path to the YAML configuration file')
    config_apply_parser.add_argument('--mode', '-m', choices=list(ALLOWED_STATES), help='Override state for all services')
    config_apply_parser.add_argument('--pull-before-start', action='store_true', default=False, help='Pull images before starting services')
    config_apply_parser.add_argument('--quiet', action='store_true', default=False, help='Use quiet mode for docker operations')

    # Service command
    service_parser = subparsers.add_parser('service', help='Manage individual services')
    service_parser.add_argument('operation', choices=list(ALLOWED_STATES), help='Operation to perform on the service')
    service_parser.add_argument('name', help='Service name in format category/name or category/subcategory/name')
    service_parser.add_argument('--pull-before-start', action='store_true', default=False, help='Pull images before starting the service')
    service_parser.add_argument('--quiet', action='store_true', default=False, help='Use quiet mode for docker operations')
    # Log-specific options
    service_parser.add_argument('--follow', '-f', action='store_true', help='Follow log output (like tail -f)')
    service_parser.add_argument('--tail', '-n', default="all", help='Number of lines to show from the end of logs (default: all)')
    service_parser.add_argument('--since', '-s', help='Show logs since timestamp (e.g., "10m" for last 10 minutes)')
    service_parser.add_argument('--timestamps', '-t', action='store_true', help='Show timestamps with log entries')

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
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        # Exit Code 130: Script terminated by Control-C
        sys.exit(130)
