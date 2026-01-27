#!/usr/bin/env python3
"""Docker services management script using YAML configuration."""

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

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DOCKER_STACKS_DIR: Path = (Path(__file__).resolve().parent.parent / "docker").resolve()
ALLOWED_OPERATIONS: tuple[str, ...] = ("pull", "up", "down", "restart", "recreate", "config", "logs")


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


def create_network_if_missing(network_name: str) -> None:
    """Create Docker network if it doesn't exist."""
    try:
        docker(["network", "inspect", network_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        logger.info(f"Creating network: {network_name}")
        docker(["network", "create", "--driver", "bridge", network_name])


def get_external_networks(compose_file: Path) -> list[str]:
    """Extract external networks from a Docker Compose file.

    Supports formats: external: true | external: {name: "..."} | name: "..."
    """
    try:
        with open(compose_file) as f:
            yaml_content = yaml.safe_load(f) or {}
    except (FileNotFoundError, yaml.YAMLError, OSError) as e:
        logger.warning(f"Error extracting networks from {compose_file}: {e}")
        return []

    networks_def = yaml_content.get("networks") or {}
    if not isinstance(networks_def, dict):
        return []

    networks: list[str] = []
    for key, cfg in networks_def.items():
        if not isinstance(cfg, dict):
            continue
        ext = cfg.get("external", False)
        name_override = cfg.get("name")
        if ext is True:
            networks.append(name_override or key)
        elif isinstance(ext, dict):
            networks.append(ext.get("name") or name_override or key)

    return list(dict.fromkeys(networks))


def create_service_networks(compose_file: Path) -> None:
    """Create all external networks required by a service."""
    for network_name in get_external_networks(compose_file):
        create_network_if_missing(network_name)


def create_localhost_link(docker_config_dir: Path) -> None:
    """Create 'localhost' symlink pointing to the current hostname directory."""
    hostname = socket.gethostname().lower()
    localhost_link = docker_config_dir / "localhost"
    hostname_dir = docker_config_dir / hostname

    if not (hostname_dir.exists() and hostname_dir.is_dir()):
        return

    if localhost_link.exists() and not localhost_link.is_symlink():
        logger.error(f"Error: {localhost_link} exists but is not a symlink. Cannot create link.")
        return

    if localhost_link.is_symlink():
        localhost_link.unlink()

    try:
        os.symlink(f"{hostname}/", localhost_link, target_is_directory=True)
    except OSError:
        logger.exception("Error creating localhost symlink")


def get_compose_file(stack_dir: Path, service_name: str) -> Path:
    """Get the yaml file path for a service."""
    return stack_dir / service_name / f"{service_name}.yaml"


def has_build_directive(compose_file: Path) -> bool:
    """Check if the compose file contains any build directives."""
    with open(compose_file) as f:
        yaml_content = yaml.safe_load(f)
    if not yaml_content:
        return False
    services = yaml_content.get("services")
    if not isinstance(services, dict):
        return False
    return any("build" in svc for svc in services.values())


def get_env_file_args(host_config_dir: Path, service_name: str) -> list[str]:
    """Get environment file arguments for Docker Compose.

    Searches for .env files in order of precedence:
    1. Common .env in config/docker
    2. Host-specific .env in config/docker/<hostname>
    3. Common service-specific .env.<service> in config/docker
    4. Host- and service-specific .env.<service> in config/docker/<hostname>
    """
    env_paths = [
        host_config_dir.parent / ".env",
        host_config_dir / ".env",
        host_config_dir.parent / f".env.{service_name}",
        host_config_dir / f".env.{service_name}",
    ]

    args: list[str] = []
    for file in env_paths:
        resolved = file.resolve()
        if resolved.is_file():
            args.extend(["--env-file", str(resolved)])
    return args


def docker(
    cmd: list[str],
    env: dict[str, str] | None = None,
    stdin: int | None = None,
    stdout: int | None = None,
    stderr: int | None = None,
) -> None:
    """Execute a docker command with the given arguments."""
    docker_bin = shutil.which("docker")
    if docker_bin is None:
        raise RuntimeError("Docker executable not found on PATH.")
    subprocess.run([docker_bin, *cmd], env=env, stdin=stdin, stdout=stdout, stderr=stderr, check=True)  # noqa: S603


def docker_pull(
    stack_dir: Path,
    service_name: str,
    compose_file: Path,
    env_file_args: list[str],
    quiet: bool = False,
) -> None:
    """Pull Docker images for a service, using build if the service has a build directive."""
    logger.info(f">>> Pulling {stack_dir}/{service_name}")

    if has_build_directive(compose_file):
        # Bake: https://docs.docker.com/guides/compose-bake/
        env = os.environ.copy()
        env["COMPOSE_BAKE"] = "true"
        cmd = ["compose", "-f", compose_file, *env_file_args, "build", "--pull"]
        if quiet:
            cmd.append("--quiet")
        docker(cmd, env=env)
    else:
        cmd = ["compose", "-f", compose_file, *env_file_args, "pull"]
        if quiet:
            cmd.append("--quiet")
        docker(cmd)


def build_log_command_flags(options: DockerOptions) -> list[str]:
    """Build Docker Compose log command flags based on options."""
    flags: list[str] = []
    if options.follow:
        flags.append("--follow")
    if options.tail and options.tail != "all":
        flags.extend(["--tail", options.tail])
    if options.since:
        flags.extend(["--since", options.since])
    if options.timestamps:
        flags.append("--timestamps")
    return flags


def docker_command(
    host_config_dir: Path,
    stack_dir: Path,
    service_name: str,
    action: str,
    options: DockerOptions | None = None,
) -> None:
    """Execute Docker Compose command for a service."""
    if options is None:
        options = DockerOptions()

    logger.info("")
    compose_file = get_compose_file(stack_dir, service_name)
    if not compose_file.exists():
        logger.error(f"Compose file not found: {compose_file}")
        return

    # Ensure external networks exist only when (re)starting containers
    if action in {"up", "recreate"}:
        create_service_networks(compose_file)

    env_file_args = get_env_file_args(host_config_dir, service_name)
    base_cmd = ["compose", "-f", compose_file, *env_file_args]

    match action:
        case "pull":
            docker_pull(stack_dir, service_name, compose_file, env_file_args, options.quiet)

        case "up":
            if options.pull_before_start:
                docker_pull(stack_dir, service_name, compose_file, env_file_args, options.quiet)
            logger.info(f">>> Starting {stack_dir}/{service_name}")
            docker([*base_cmd, "up", "--detach"])

        case "down":
            logger.info(f">>> Stopping {stack_dir}/{service_name}")
            docker([*base_cmd, "down"])

        case "restart":
            logger.info(f">>> Restarting {stack_dir}/{service_name}")
            docker([*base_cmd, "restart"])

        case "recreate":
            if options.pull_before_start:
                docker_pull(stack_dir, service_name, compose_file, env_file_args, options.quiet)
            logger.info(f">>> Recreating {stack_dir}/{service_name}")
            docker([*base_cmd, "up", "--detach", "--force-recreate"])

        case "config":
            logger.info(f">>> Checking {stack_dir}/{service_name}")
            docker([*base_cmd, "config"])

        case "logs":
            logger.info(f">>> Showing logs for {stack_dir}/{service_name}")
            docker([*base_cmd, "logs", *build_log_command_flags(options)])


def load_services_config(config_file: str | Path) -> dict:
    """Load services configuration from YAML file."""
    try:
        with open(config_file) as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        logger.exception(f"Error loading configuration file {config_file}")
        sys.exit(1)


def process_services(
    host_config_dir: Path,
    config: dict,
    state_override: str | None = None,
    pull_before_start: bool = False,
    quiet: bool = False,
) -> None:
    """Process services based on the configuration."""
    if not isinstance(config, dict):
        logger.error("Error: Invalid configuration format. Config must be a dict.")
        return

    if "services" not in config:
        logger.error("Error: Invalid configuration format. 'services' key not found.")
        return

    if not isinstance(config["services"], list):
        logger.error("Error: Invalid configuration format. 'services' must be a list.")
        return

    options = DockerOptions(pull_before_start=pull_before_start, quiet=quiet)

    for category_entry in config["services"]:
        # Each entry should have a single key (the category name) and a list of services
        if not isinstance(category_entry, dict) or len(category_entry) != 1:
            logger.warning(f"Skipping invalid category entry: {category_entry}")
            continue

        category = next(iter(category_entry.keys()))
        service_list = category_entry[category]

        if not isinstance(service_list, list):
            logger.warning(f"Skipping category '{category}': services value is not a list")
            continue

        # Process each service in this category
        for service in service_list:
            if not isinstance(service, dict):
                logger.warning(f"Skipping invalid service entry in category {category}: expected dict, got {type(service).__name__}")
                continue

            name = service.get("name", "")
            if not name:
                logger.warning(f"Skipping invalid service entry in category {category}: missing name")
                continue

            state = (state_override or service.get("state", "up")).lower()
            if state not in ALLOWED_OPERATIONS:
                logger.warning(f"Unknown state '{state}' for service {category}/{name}")
                continue

            docker_command(host_config_dir, DOCKER_STACKS_DIR / category, name, state, options)


def get_host_config_dir() -> Path:
    """Get the host-specific Docker configuration directory."""
    hostname = socket.gethostname().lower()
    script_dir = Path(__file__).parent.absolute()
    return script_dir.parent / "config" / "docker" / hostname


def cmd_config_apply(args: argparse.Namespace) -> None:
    """Apply configuration to Docker services."""
    if args.config:
        config_file = Path(args.config)
        host_config_dir = config_file.parent
    else:
        # Use the default location based on hostname
        host_config_dir = get_host_config_dir()
        config_file = host_config_dir / "services.yaml"

    logger.info("Init...")
    config = load_services_config(config_file)
    create_localhost_link(host_config_dir.parent)
    process_services(host_config_dir, config, args.mode, args.pull_before_start, args.quiet)


def cmd_service(args: argparse.Namespace) -> None:
    """Manage individual Docker services."""
    if not args.name:
        logger.error("Service name is required")
        sys.exit(1)

    name_parts = args.name.split("/")
    if len(name_parts) < 2:
        logger.error("Service name must be in format category/name or category/subcategory/name")
        sys.exit(1)

    service_name = name_parts[-1]
    category_path = "/".join(name_parts[:-1])

    options = DockerOptions(
        pull_before_start=args.pull_before_start,
        quiet=args.quiet,
        follow=getattr(args, "follow", False),
        tail=getattr(args, "tail", "all"),
        since=getattr(args, "since", None),
        timestamps=getattr(args, "timestamps", False),
    )

    docker_command(get_host_config_dir(), DOCKER_STACKS_DIR / category_path, service_name, args.operation, options)


def main() -> None:
    """Main entry point for the Docker services management CLI."""
    parser = argparse.ArgumentParser(description="Manage Docker services using YAML configuration.")
    subparsers = parser.add_subparsers(dest="command", help="Commands", required=True)

    # Config command with apply subcommand
    config_parser = subparsers.add_parser("config", help="Manage service configurations")
    config_subparsers = config_parser.add_subparsers(dest="config_command", help="Config subcommands", required=True)

    config_apply_parser = config_subparsers.add_parser("apply", help="Apply service configurations")
    config_apply_parser.add_argument("--config", "-c", help="Path to the YAML configuration file")
    config_apply_parser.add_argument("--mode", "-m", choices=list(ALLOWED_OPERATIONS), help="Override state for all services")
    config_apply_parser.add_argument("--pull-before-start", action="store_true", help="Pull images before starting services")
    config_apply_parser.add_argument("--quiet", action="store_true", help="Use quiet mode for docker operations")

    # Service command
    service_parser = subparsers.add_parser("service", help="Manage individual services")
    service_parser.add_argument("operation", choices=list(ALLOWED_OPERATIONS), help="Operation to perform on the service")
    service_parser.add_argument("name", help="Service name in format category/name or category/subcategory/name")
    service_parser.add_argument("--pull-before-start", action="store_true", help="Pull images before starting the service")
    service_parser.add_argument("--quiet", action="store_true", help="Use quiet mode for docker operations")
    # Log-specific options
    service_parser.add_argument("--follow", "-f", action="store_true", help="Follow log output (like tail -f)")
    service_parser.add_argument("--tail", "-n", default="all", help="Number of lines to show from the end of logs (default: all)")
    service_parser.add_argument("--since", "-s", help='Show logs since timestamp (e.g., "10m" for last 10 minutes)')
    service_parser.add_argument("--timestamps", "-t", action="store_true", help="Show timestamps with log entries")

    args = parser.parse_args()

    match args.command:
        case "config" if args.config_command == "apply":
            cmd_config_apply(args)
        case "service":
            cmd_service(args)
        case _:
            parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
        # Exit Code 130: Script terminated by Control-C
        sys.exit(130)
