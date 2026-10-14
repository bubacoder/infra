"""Shared DNS checkpoint verification for bootstrap targets."""

import socket

from .core import AwsPlan, BootstrapError, BootstrapPlan


def verify_dns(plan: BootstrapPlan | AwsPlan, expected: str, *, discovered: bool = False) -> None:
    """Require the base and bootstrap service names to resolve only to expected."""
    names = [plan.config.network.domain, *(f"{name}.{plan.config.network.domain}" for name in ("traefik", "home", "bootstrap-check"))]
    failures = []
    for name in names:
        try:
            addresses = {entry[4][0] for entry in socket.getaddrinfo(name, None, socket.AF_INET)}
        except socket.gaierror:
            addresses = set()
        if addresses != {expected}:
            failures.append(name)
    if not failures:
        return
    if isinstance(plan, AwsPlan):
        raise BootstrapError(
            f"AWS DNS checkpoint: point the base domain and wildcard directly to Elastic IP {expected} using DNS-only records, then rerun bootstrap. Required names: {', '.join(names)}"
        )
    if discovered:
        raise BootstrapError(
            f"Networking checkpoint: VM {plan.vm_id} was discovered at {expected}. Ask the operator to map its base domain and service names to that address, then rerun bootstrap. Required names: {', '.join(names)}"
        )
    raise BootstrapError(
        f"External DHCP/DNS checkpoint is incomplete. Reserve {plan.mac} as {expected}, then point the base domain and wildcard to that address. Failed names: {', '.join(failures)}"
    )
