#!/usr/bin/env python3
"""Safely configure Guacamole's persisted native OIDC settings."""

import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROPERTY_PATH = "/config/guacamole/guacamole.properties"
ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def load_env_file(path: Path, values: dict[str, str]) -> None:
    """Load simple dotenv assignments without executing host configuration."""
    if not path.is_file():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            values[key] = value.strip().strip("\"'")


def host_environment(host: str) -> dict[str, str]:
    """Load common and host-specific Guacamole environment files."""
    docker_config = ROOT / "config/docker"
    host_dir = docker_config / host
    if not host_dir.is_dir():
        raise ValueError(f"Host configuration directory does not exist: {host_dir}")
    values = dict(os.environ)
    for path in (docker_config / ".env", host_dir / ".env", docker_config / ".env.guacamole", host_dir / ".env.guacamole"):
        load_env_file(path, values)
    return values


def expand(value: str, env: dict[str, str]) -> str:
    """Expand dotenv-style variables, rejecting missing and circular values."""
    expanded = value
    seen: set[str] = set()
    while ENV_PATTERN.search(expanded):
        if expanded in seen:
            raise ValueError(f"Circular environment variable expansion: {value}")
        seen.add(expanded)

        def replacement(match: re.Match[str]) -> str:
            key = match.group(1)
            if not env.get(key):
                raise ValueError(f"Required environment variable is unset: {key}")
            return env[key]

        expanded = ENV_PATTERN.sub(replacement, expanded)
    return expanded


def desired_properties(env: dict[str, str]) -> dict[str, str]:
    """Build non-secret OIDC properties from the configured domain and client ID."""
    domain = expand("${MYDOMAIN}", env)
    client_id = expand("${GUACAMOLE_AUTHENTIK_CLIENT_ID}", env)
    issuer = f"https://sso.{domain}/application/o/guacamole/"
    return {
        "openid-authorization-endpoint": "https://sso." + domain + "/application/o/authorize/",
        "openid-jwks-endpoint": issuer + "jwks/",
        "openid-issuer": issuer,
        "openid-client-id": client_id,
        "openid-redirect-uri": f"https://guacamole.{domain}",
        "openid-username-claim-type": "email",
        "postgresql-auto-create-accounts": "true",
        "extension-priority": "*, openid",
    }


def parse_properties(content: str) -> dict[str, str]:
    """Parse Guacamole's colon-separated properties without touching other keys."""
    properties = {}
    for line in content.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() and not key.lstrip().startswith("#"):
            properties[key.strip()] = value.strip()
    return properties


def update_properties(content: str, desired: dict[str, str]) -> str:
    """Replace only declared OIDC keys and append any that are absent."""
    remaining = dict(desired)
    lines = []
    for line in content.splitlines():
        key, separator, _ = line.partition(":")
        normalized = key.strip()
        if separator and normalized in remaining:
            lines.append(f"{normalized}: {remaining.pop(normalized)}")
        else:
            lines.append(line)
    lines.extend(f"{key}: {value}" for key, value in remaining.items())
    return "\n".join(lines) + "\n"


def run(command: list[str]) -> str:
    """Run Docker commands with errors surfaced to the operator."""
    return subprocess.run(command, check=True, text=True, capture_output=True).stdout  # noqa: S603


def read_properties(container: str) -> str:
    """Read the persisted configuration through Docker without exposing it in output."""
    with tempfile.TemporaryDirectory() as directory:
        destination = Path(directory) / "guacamole.properties"
        run(["docker", "cp", f"{container}:{PROPERTY_PATH}", str(destination)])
        return destination.read_text()


def write_properties(container: str, content: str) -> None:
    """Atomically replace the configuration and restore the image's expected owner."""
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "guacamole.properties"
        source.write_text(content)
        run(["docker", "cp", str(source), f"{container}:{PROPERTY_PATH}"])
    run(["docker", "exec", container, "chown", "tomcat:tomcat", PROPERTY_PATH])


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or apply Guacamole native OIDC configuration.")
    parser.add_argument("--host", required=True, help="Host directory name beneath config/docker")
    parser.add_argument("--container", default="guacamole", help="Guacamole container name")
    parser.add_argument("--apply", action="store_true", help="Write the declared OIDC properties")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.container):
        parser.error("--container must be a Docker container name")
    try:
        desired = desired_properties(host_environment(args.host))
        current_content = read_properties(args.container)
        current = parse_properties(current_content)
        changed = [key for key, value in desired.items() if current.get(key) != value]
        for key in desired:
            print(("UPDATE" if key in changed else "NO-CHANGE") + f" {key}")
        if args.apply and changed:
            write_properties(args.container, update_properties(current_content, desired))
            print("APPLIED Guacamole OIDC properties")
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"Error: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
