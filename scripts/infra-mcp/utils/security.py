"""
Security utilities for validating and protecting against various attack vectors.
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def validate_url_for_ssrf(url: str) -> bool:  # noqa: PLR0911
    """
    SSRF guard: validate URL to block potentially unsafe requests.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if URL is safe, False if it should be blocked.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        logger.warning("Blocked potentially unsafe URL=%r (invalid scheme)", url)
        return False

    hostname = parsed.hostname
    if not hostname:
        logger.warning("Blocked potentially unsafe URL=%r (missing hostname)", url)
        return False

    if hostname in {"localhost", "127.0.0.1"}:
        logger.warning("Blocked potentially unsafe URL=%r (localhost)", url)
        return False

    try:
        # First, see if hostname is already an IP literal
        resolved_ips = [ipaddress.ip_address(hostname)]
    except ValueError:
        # Not a literal IP, so resolve via DNS
        try:
            addrinfo = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            logger.warning("Blocked potentially unsafe URL=%r (unresolvable host)", url)
            return False

        resolved_ips = []
        for _family, _, _, _, sockaddr in addrinfo:
            if not sockaddr:
                continue
            ip_str = sockaddr[0]
            try:
                resolved_ips.append(ipaddress.ip_address(ip_str))
            except ValueError:
                # Skip any non-IP entries
                continue

    # If resolution yielded nothing, block as unresolvable
    if not resolved_ips:
        logger.warning("Blocked potentially unsafe URL=%r (unresolvable host)", url)
        return False

    # Finally, vet every resolved IP against disallowed ranges
    for resolved_ip in resolved_ips:
        if (
            resolved_ip.is_loopback
            or resolved_ip.is_private
            or resolved_ip.is_link_local
            or resolved_ip.is_reserved
            or resolved_ip.is_multicast
            or resolved_ip.is_unspecified
        ):
            logger.warning("Blocked potentially unsafe URL=%r (private/reserved IP)", url)
            return False

    return True
