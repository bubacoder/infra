#!/usr/bin/env python3
"""Split host Docker environment values by Compose deployment usage."""

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ENV_REFERENCE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::[-?][^}]*)?\}")
ENV_ASSIGNMENT = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=")


@dataclass
class EnvironmentEntry:
    """One active dotenv assignment with its leading documentation."""

    name: str
    value: str
    lines: list[str]


def environment_entries(path: Path) -> tuple[list[EnvironmentEntry], list[str]]:
    """Read active dotenv assignments without interpreting their values."""
    entries: list[EnvironmentEntry] = []
    pending: list[str] = []
    for line in path.read_text().splitlines():
        match = ENV_ASSIGNMENT.match(line)
        if not match:
            pending.append(line)
            continue
        name = match.group(1)
        value = line.split("=", 1)[1]
        entries.append(EnvironmentEntry(name, value, [*pending, line]))
        pending = []
    return entries, pending


def references(value: object) -> set[str]:
    """Return Compose-style variable references from a scalar value."""
    return set(ENV_REFERENCE.findall(value)) if isinstance(value, str) else set()


def walk_references(value: object) -> set[str]:
    """Collect interpolations recursively from parsed Compose data."""
    if isinstance(value, dict):
        return set().union(*(walk_references(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(walk_references(item) for item in value))
    return references(value)


def compose_consumers(stacks_dir: Path) -> dict[str, set[str]]:
    """Map each Compose variable to the stack names that interpolate it."""
    consumers: dict[str, set[str]] = defaultdict(set)
    for path in stacks_dir.rglob("*.yaml"):
        service = path.parent.name
        if path.name not in {f"{service}.yaml"} and not path.name.startswith(f"{service}-"):
            continue
        try:
            document = yaml.safe_load(path.read_text())
        except yaml.YAMLError as error:
            raise ValueError(f"Cannot parse Compose file {path}: {error}") from error
        for variable in walk_references(document):
            consumers[variable].add(service)
    return consumers


def expand_consumers(entries: list[EnvironmentEntry], consumers: dict[str, set[str]]) -> dict[str, set[str]]:
    """Propagate service usage through dotenv values such as STORAGE_MEDIA=${STORAGE_LOCAL}/media."""
    by_name = {entry.name: entry for entry in entries}
    expanded = {name: set(services) for name, services in consumers.items()}
    changed = True
    while changed:
        changed = False
        for entry in entries:
            for dependency in references(entry.value):
                if dependency not in by_name:
                    continue
                before = len(expanded.setdefault(dependency, set()))
                expanded[dependency].update(expanded.get(entry.name, set()))
                changed |= len(expanded[dependency]) != before
    return expanded


def defined_names(path: Path) -> set[str]:
    """Return active assignment names already present in a dotenv file."""
    if not path.exists():
        return set()
    return {entry.name for entry in environment_entries(path)[0]}


def render(entries: list[EnvironmentEntry], trailing: list[str]) -> str:
    """Render source lines while preserving their documented values."""
    lines = [line for entry in entries for line in entry.lines]
    lines.extend(trailing)
    return "\n".join(lines).rstrip() + "\n"


def split_environment(host_dir: Path, stacks_dir: Path, write: bool = True) -> dict[str, object]:
    """Split host_dir/.env into common, non-Compose, and per-service files."""
    main_env = host_dir / ".env"
    if not main_env.is_file():
        raise ValueError(f"Host environment file does not exist: {main_env}")

    entries, trailing = environment_entries(main_env)
    consumers = expand_consumers(entries, compose_consumers(stacks_dir))
    common: list[EnvironmentEntry] = []
    operational: list[EnvironmentEntry] = []
    service_entries: dict[str, list[EnvironmentEntry]] = defaultdict(list)

    for entry in entries:
        used_by = consumers.get(entry.name, set())
        if len(used_by) > 1:
            common.append(entry)
        elif len(used_by) == 1:
            service_entries[next(iter(used_by))].append(entry)
        else:
            operational.append(entry)

    # Variables read before Compose starts (for example GPU_COMPOSE_SUFFIX) are not references.
    operational_names = {entry.name for entry in operational}
    main_entries = [*common]
    if operational:
        main_entries.append(
            EnvironmentEntry(
                "__SECTION__",
                "",
                ["", "# Operational settings not consumed by Docker Compose deployments"],
            )
        )
        main_entries.extend(operational)

    result = {"common": [entry.name for entry in common], "operational": sorted(operational_names)}
    result["services"] = {service: [entry.name for entry in values] for service, values in sorted(service_entries.items())}

    if not write:
        return result

    for service, values in service_entries.items():
        target = host_dir / f".env.{service}"
        existing_names = defined_names(target)
        additions = [entry for entry in values if entry.name not in existing_names]
        if not additions:
            continue
        prefix = [] if target.exists() else [f"# Environment variables for {service}", ""]
        existing = target.read_text().rstrip() if target.exists() else ""
        addition_lines = [line for entry in additions for line in entry.lines]
        while addition_lines and not addition_lines[0]:
            addition_lines.pop(0)
        content = "\n".join([*prefix, *addition_lines]).strip()
        separator = "\n" if existing else ""
        if not target.exists():
            target.touch(mode=0o600)
        target.write_text(f"{existing}\n{separator}{content}\n")
    main_env.write_text(render(main_entries, trailing))
    return result


def main() -> int:
    """Parse CLI arguments and split a host Docker environment file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host_dir", type=Path, help="Directory containing the host .env file")
    parser.add_argument("--stacks-dir", type=Path, default=ROOT / "docker", help="Docker Compose stacks directory")
    parser.add_argument("--check", action="store_true", help="Report the planned split without modifying files")
    args = parser.parse_args()
    try:
        split_environment(args.host_dir, args.stacks_dir, write=not args.check)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
