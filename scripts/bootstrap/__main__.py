#!/usr/bin/env python3
"""Plan and apply the supported first-time homelab deployment."""

import argparse
import sys
from pathlib import Path

from . import aws, config, deploy, inspect_config, proxmox
from .core import DEFAULT_CONFIG, BootstrapError, ConfigError, Runner


def parse_args() -> argparse.Namespace:
    """Parse bootstrap command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Bootstrap YAML path")
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--show-config", action="store_true", help="Print allowlisted, redacted settings offline without deployment validation")
    operation.add_argument("--plan", action="store_true", help="Validate and print a redacted plan")
    operation.add_argument("--apply", action="store_true", help="Apply or resume the deployment")
    parser.add_argument("--yes", action="store_true", help="Skip the apply confirmation prompt")
    return parser.parse_args()


def main() -> None:
    """Validate, plan, and optionally apply the configured bootstrap."""
    args = parse_args()
    if args.yes and not args.apply:
        raise ConfigError("--yes requires --apply")
    if args.show_config:
        inspect_config.show(args.config)
        return
    runner = Runner()
    bootstrap_config = config.load_config(args.config)
    if bootstrap_config.target == "aws":
        with aws.deployment_lock(bootstrap_config):
            plan = aws.resolve_plan(bootstrap_config, runner)
            aws.preflight(plan, runner)
            print("Preflight passed. No cloud resources have been changed.")
            if args.apply:
                aws.apply(plan, runner, assume_yes=args.yes)
        return
    plan = proxmox.resolve_plan(bootstrap_config, runner)
    proxmox.print_plan(plan)
    proxmox.preflight(plan, runner)
    print("Preflight passed.")
    if args.apply:
        deploy.apply(plan, runner, assume_yes=args.yes)


if __name__ == "__main__":
    try:
        main()
    except (BootstrapError, ConfigError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
