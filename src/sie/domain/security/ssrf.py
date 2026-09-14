"""SSRF Protection utilities.

Provides URL validation to prevent Server-Side Request Forgery attacks
by blocking requests to internal/private network addresses.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

_PRIVATE_IPV4_NETWORKS = [
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("0.0.0.0/8"),
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("169.254.0.0/16"),
    ipaddress.IPv4Network("100.64.0.0/10"),
    ipaddress.IPv4Network("192.0.0.0/24"),
    ipaddress.IPv4Network("192.0.2.0/24"),
    ipaddress.IPv4Network("198.51.100.0/24"),
    ipaddress.IPv4Network("203.0.113.0/24"),
    ipaddress.IPv4Network("224.0.0.0/4"),
    ipaddress.IPv4Network("240.0.0.0/4"),
    ipaddress.IPv4Network("255.255.255.255/32"),
]

_PRIVATE_IPV6_NETWORKS = [
    ipaddress.IPv6Network("::1/128"),
    ipaddress.IPv6Network("::/128"),
    ipaddress.IPv6Network("::ffff:0:0/96"),
    ipaddress.IPv6Network("64:ff9b::/96"),
    ipaddress.IPv6Network("fe80::/10"),
    ipaddress.IPv6Network("fc00::/7"),
    ipaddress.IPv6Network("ff00::/8"),
    ipaddress.IPv6Network("2001:db8::/32"),
    ipaddress.IPv6Network("2001:10::/28"),
    ipaddress.IPv6Network("2001:20::/28"),
]

_CLOUD_METADATA_IPS = [
    ipaddress.IPv4Address("169.254.169.254"),
    ipaddress.IPv6Address("fd00:ec2::254"),
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
    """Validate a hostname/IP for outbound requests."""
    try:
        ip = ipaddress.ip_address(hostname)
        if is_cloud_metadata_ip(ip):
            return False, f"Cloud metadata endpoint blocked: {ip}"
        if is_private_ip(ip):
            if allow_localhost and ip in {
                ipaddress.IPv4Address("127.0.0.1"),
                ipaddress.IPv6Address("::1"),
            }:
                return True, None
            return False, f"Private/internal IP blocked: {ip}"
    except ValueError:
        if not allow_localhost and hostname.lower() in ("localhost", "localhost.localdomain"):
            return False, "Localhost blocked"
    return True, None


def validate_url(
    url: str,
    allow_localhost: bool = False,
    allowed_schemes: tuple[str, ...] = ("http", "https"),
) -> tuple[bool, str | None]:
    """Validate URL syntax and reject known unsafe literal hosts."""
    try:
        parsed = urlparse(url)
    except Exception as exc:
        return False, f"Invalid URL: {exc}"

    if parsed.scheme not in allowed_schemes:
        return False, f"Scheme '{parsed.scheme}' not allowed. Allowed: {allowed_schemes}"

    hostname = parsed.hostname
    if not hostname:
        return False, "URL missing hostname"

    return is_safe_hostname(hostname, allow_localhost=allow_localhost)


async def resolve_and_validate(url: str, allow_localhost: bool = False) -> tuple[bool, str | None]:
    """Resolve a hostname and reject unsafe resolved addresses.

    This catches the common DNS-based SSRF case where a public-looking
    hostname resolves to a private, loopback, link-local, or metadata address.
    It is a pre-request check and does not eliminate a resolver-level TOCTOU
    race between DNS resolution and the eventual socket connection.
    """
    safe, error = validate_url(url, allow_localhost=allow_localhost)
    if not safe:
        return False, error

    hostname = urlparse(url).hostname
    if not hostname:
        return False, "URL missing hostname"

    try:
        ipaddress.ip_address(hostname)
        return True, None
    except ValueError:
        pass

    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )
    except (socket.gaierror, OSError) as exc:
        return False, f"DNS resolution failed for {hostname}: {exc}"

    addresses = {sockaddr[0] for _family, _type, _proto, _canonname, sockaddr in infos}
    if not addresses:
        return False, f"DNS resolution returned no addresses for {hostname}"

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False, f"DNS returned invalid address for {hostname}: {address}"

        if is_cloud_metadata_ip(ip):
            return False, f"DNS resolved {hostname} to cloud metadata endpoint: {ip}"
        if is_private_ip(ip):
            if allow_localhost and ip in {
                ipaddress.IPv4Address("127.0.0.1"),
                ipaddress.IPv6Address("::1"),
            }:
                continue
            return False, f"DNS resolved {hostname} to private/internal IP: {ip}"

    return True, None
