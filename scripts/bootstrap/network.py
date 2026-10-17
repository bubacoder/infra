"""Shared DNS checkpoint verification for bootstrap targets."""

import socket
import time

from .core import AwsPlan, BootstrapError, ProxmoxPlan


def verify_dns(plan: ProxmoxPlan | AwsPlan, expected: str, *, discovered: bool = False, wait_seconds: int = 0) -> None:
    """Require the base and bootstrap service names to resolve only to expected."""
    domain = plan.config.network.domain
    names = [domain, *(f"{name}.{domain}" for name in ("traefik", "home", "bootstrap-check"))]
    deadline = time.monotonic() + wait_seconds
    while True:
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
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(2, remaining))
    if plan.config.network.dns.enabled:
        raise BootstrapError(
            f"Managed DNS resolver checkpoint: required names do not resolve only to {expected}: {', '.join(failures)}. "
            "Check resolver selection, caches and filtering. Existing DNS changes and infrastructure remain intact; no hosts-file fallback is supported."
        )
    if isinstance(plan, AwsPlan):
        raise BootstrapError(
            f"AWS DNS checkpoint: point the base domain and wildcard directly to Elastic IP {expected} using DNS-only records. "
            "If a local resolver overrides this domain, configure its answers too. "
            "Default Cloudflare/AdGuard automation uses network.dns.enabled: true; see docs/bootstrap-dns.md. "
            f"Then rerun bootstrap. Required names: {', '.join(names)}"
        )
    if discovered:
        raise BootstrapError(
            f"Networking checkpoint: VM {plan.vm_id} was discovered at {expected}. Configure local DNS for its base domain and service names, then rerun bootstrap. Required names: {', '.join(names)}"
        )
    raise BootstrapError(
        f"External DHCP/DNS checkpoint is incomplete. Reserve {plan.mac} as {expected}, then point the base domain and wildcard to that address. Failed names: {', '.join(failures)}"
    )
