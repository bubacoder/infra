#!/usr/bin/env python3
"""Reconcile Gitea's database-stored Authentik OIDC authentication source.

Gitea external authentication sources are persisted in its database rather than
Compose configuration. This helper creates or updates the `authentik` source
from ignored host credentials without exposing the client secret in shell
history. It never deletes sources or users.
"""

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

# docker/dev/gitea/gitea-auth.py -> repository root
ROOT = Path(__file__).resolve().parents[3]
VARIABLE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def load_env(path: Path, values: dict[str, str]) -> None:
    """Read simple dotenv assignments without executing configuration."""
    if not path.is_file():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")


def expand(value: str, values: dict[str, str]) -> str:
    for _ in range(10):
        expanded = VARIABLE.sub(lambda match: values.get(match.group(1), match.group(0)), value)
        if expanded == value:
            return expanded
        value = expanded
    return value


def host_environment(host: str) -> dict[str, str]:
    docker_config = ROOT / "config" / "docker"
    host_dir = docker_config / host
    values = dict(os.environ)
    for path in (docker_config / ".env", host_dir / ".env", docker_config / ".env.gitea", host_dir / ".env.gitea"):
        load_env(path, values)
    return {key: expand(value, values) for key, value in values.items()}


def required(values: dict[str, str], name: str) -> str:
    value = values.get(name, "")
    if not value:
        raise ValueError(f"{name} is required in the host Docker environment")
    return value


def run_gitea(*args: str) -> subprocess.CompletedProcess[str]:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("docker executable is required")
    # Values are individual arguments, never evaluated by a shell.
    return subprocess.run(  # noqa: S603
        [docker, "exec", "--user", "git", "gitea", "gitea", "admin", "auth", *args],
        check=True,
        text=True,
        capture_output=True,
    )


def source_id(output: str, name: str) -> str | None:
    for line in output.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 4 and fields[1] == name:
            return fields[0]
    return None


def source_args(values: dict[str, str]) -> list[str]:
    domain = required(values, "MYDOMAIN")
    # fmt: off
    return [
        "--name", "authentik",
        "--provider", "openidConnect",
        "--key", required(values, "GITEA_AUTHENTIK_CLIENT_ID"),
        "--secret", required(values, "GITEA_AUTHENTIK_CLIENT_SECRET"),
        "--auto-discover-url", f"https://sso.{domain}/application/o/gitea/.well-known/openid-configuration",
        "--scopes", "openid",
        "--scopes", "profile",
        "--scopes", "email",
        "--required-claim-name", "groups",
        "--required-claim-value", "developers",
        "--group-claim-name", "groups",
    ]
    # fmt: on


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile Gitea's Authentik OIDC authentication source")
    parser.add_argument("--host", required=True, help="Host directory name beneath config/docker")
    parser.add_argument("--apply", action="store_true", help="Create or update the authentication source")
    args = parser.parse_args()

    values = host_environment(args.host)
    existing = source_id(run_gitea("list").stdout, "authentik")
    action = "UPDATE" if existing else "CREATE"
    print(f"{action} Gitea Authentik OIDC source")
    if not args.apply:
        return
    command = ["update-oauth", "--id", existing] if existing else ["add-oauth"]
    run_gitea(*command, *source_args(values))
    print("APPLIED Gitea Authentik OIDC source")


if __name__ == "__main__":
    main()
