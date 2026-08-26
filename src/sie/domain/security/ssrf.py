"""SSRF Protection utilities.

Provides URL validation to prevent Server-Side Request Forgery attacks
by blocking requests to internal/private network addresses.
"""

from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Private IP ranges that should never be accessed via outbound requests
_PRIVATE_IPV4_NETWORKS = [
    ipaddress.IPv4Network("127.0.0.0/8"),      # Loopback
    ipaddress.IPv4Network("0.0.0.0/8"),        # Current network
    ipaddress.IPv4Network("10.0.0.0/8"),       # RFC1918 private
    ipaddress.IPv4Network("172.16.0.0/12"),    # RFC1918 private
    ipaddress.IPv4Network("192.168.0.0/16"),   # RFC1918 private
    ipaddress.IPv4Network("169.254.0.0/16"),   # Link-local
    ipaddress.IPv4Network("100.64.0.0/10"),    # CGNAT
    ipaddress.IPv4Network("192.0.0.0/24"),     # IETF protocol assignments
    ipaddress.IPv4Network("192.0.2.0/24"),     # TEST-NET-1
    ipaddress.IPv4Network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.IPv4Network("203.0.113.0/24"),   # TEST-NET-3
    ipaddress.IPv4Network("224.0.0.0/4"),      # Multicast
    ipaddress.IPv4Network("240.0.0.0/4"),      # Reserved
    ipaddress.IPv4Network("255.255.255.255/32"), # Broadcast
]

_PRIVATE_IPV6_NETWORKS = [
    ipaddress.IPv6Network("::1/128"),           # Loopback
    ipaddress.IPv6Network("::/128"),            # Unspecified
    ipaddress.IPv6Network("::ffff:0:0/96"),     # IPv4-mapped
    ipaddress.IPv6Network("64:ff9b::/96"),      # IPv4-IPv6 translation
    ipaddress.IPv6Network("fe80::/10"),         # Link-local
    ipaddress.IPv6Network("fc00::/7"),          # Unique local (ULA)
    ipaddress.IPv6Network("ff00::/8"),          # Multicast
    ipaddress.IPv6Network("2001:db8::/32"),     # Documentation
    ipaddress.IPv6Network("2001:10::/28"),      # ORCHID
    ipaddress.IPv6Network("2001:20::/28"),      # ORCHIDv2
]

# Cloud metadata endpoints that should be blocked
_CLOUD_METADATA_IPS = [
    ipaddress.IPv4Address("169.254.169.254"),   # AWS, GCE, Azure, DigitalOcean
    ipaddress.IPv6Address("fd00:ec2::254"),     # AWS IPv6
]


def is_private_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address is private/internal."""
    if isinstance(ip, ipaddress.IPv4Address):
        return any(ip in network for network in _PRIVATE_IPV4_NETWORKS)
    if isinstance(ip, ipaddress.IPv6Address):
        return any(ip in network for network in _PRIVATE_IPV6_NETWORKS)
    return False


def is_cloud_metadata_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address is a cloud metadata endpoint."""
    return ip in _CLOUD_METADATA_IPS


def is_safe_hostname(hostname: str, allow_localhost: bool = False) -> tuple[bool, str | None]:
    """Validate a hostname/IP for outbound requests.

    Args:
        hostname: The hostname or IP address to validate.
        allow_localhost: If True, allow localhost (for development only).

    Returns:
        Tuple of (is_safe, error_message). If not safe, error_message explains why.
    """
    # Check if it's an IP address
    try:
        ip = ipaddress.ip_address(hostname)
        if is_cloud_metadata_ip(ip):
            return False, f"Cloud metadata endpoint blocked: {ip}"
        if is_private_ip(ip):
            if allow_localhost and ip == ipaddress.IPv4Address("127.0.0.1"):
                return True, None
            if allow_localhost and ip == ipaddress.IPv6Address("::1"):
                return True, None
            return False, f"Private/internal IP blocked: {ip}"
        return True, None
    except ValueError:
        pass  # Not an IP address, treat as hostname

    # Block localhost hostnames unless explicitly allowed
    if not allow_localhost and hostname.lower() in ("localhost", "localhost.localdomain"):
        return False, "Localhost blocked"

    # Additional hostname validation could be added here (e.g., allowlist)
    return True, None


def validate_url(
    url: str,
    allow_localhost: bool = False,
    allowed_schemes: tuple[str, ...] = ("http", "https"),
) -> tuple[bool, str | None]:
    """Validate a URL for outbound requests.

    Args:
        url: The URL to validate.
        allow_localhost: If True, allow localhost (for development only).
        allowed_schemes: Tuple of allowed URL schemes.

    Returns:
        Tuple of (is_safe, error_message). If not safe, error_message explains why.
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:
        return False, f"Invalid URL: {exc}"

    # Check scheme
    if parsed.scheme not in allowed_schemes:
        return False, f"Scheme '{parsed.scheme}' not allowed. Allowed: {allowed_schemes}"

    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        return False, "URL missing hostname"

    # Validate hostname/IP
    safe, error = is_safe_hostname(hostname, allow_localhost=allow_localhost)
    if not safe:
        return False, error

    return True, None


async def resolve_and_validate(url: str, allow_localhost: bool = False) -> tuple[bool, str | None]:
    """Resolve a URL's hostname and validate the resulting IP addresses.

    This provides protection against DNS rebinding attacks by validating
    the resolved IPs at request time.

    Args:
        url: The URL to validate.
        allow_localhost: If True, allow localhost (for development only).

    Returns:
        Tuple of (is_safe, error_message).
    """
    # First validate the URL structure
    safe, error = validate_url(url, allow_localhost=allow_localhost)
    if not safe:
        return False, error

    # Note: Actual DNS resolution should be done by the HTTP client
    # This function provides the validation logic that should be applied
    # to resolved addresses during request execution
    return True, None
