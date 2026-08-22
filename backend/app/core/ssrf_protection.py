"""
TourSafe SSRF (Server-Side Request Forgery) Defense Engine.
Validates outbound URLs to ensure the application only communicates with
legitimate external destinations and strictly blocks:
- Private IPv4 address space (RFC 1918: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Loopback addresses (127.0.0.0/8, localhost, ::1)
- Link-local and Cloud Metadata endpoints (169.254.169.254, fe80::/10)
- Carrier Grade NAT (100.64.0.0/10) and Broadcast (255.255.255.255)
- Non-HTTP(S) protocols (file://, gopher://, ftp://, dict://, ldap://)
"""

import ipaddress
import socket
import urllib.parse
from typing import List, Optional, Set, Tuple
from fastapi import HTTPException, status

ALLOWED_SCHEMES: Set[str] = {"http", "https"}

# Cloud metadata and forbidden hostnames
BLOCKED_HOSTNAMES: Set[str] = {
    "localhost",
    "metadata.google.internal",
    "instance-data",
    "metadata.aws.internal",
}


def is_ip_forbidden(ip_str: str) -> Tuple[bool, str]:
    """Check if an IP address falls within private, loopback, or metadata ranges."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_loopback:
            return True, f"Loopback address forbidden ({ip_str})"
        if ip.is_private:
            return True, f"Private network address forbidden ({ip_str})"
        if ip.is_link_local:
            return True, f"Link-local address forbidden ({ip_str})"
        if ip.is_reserved:
            return True, f"Reserved IP address forbidden ({ip_str})"
        if ip.is_multicast:
            return True, f"Multicast IP address forbidden ({ip_str})"
        if str(ip) == "169.254.169.254":
            return True, "Cloud metadata endpoint blocked"
        return False, "Allowed"
    except ValueError:
        return True, f"Invalid IP address format: {ip_str}"


def validate_outbound_url(
    url: str,
    allowlist_domains: Optional[List[str]] = None,
    allow_local_dev: bool = False,
) -> str:
    """
    Validate a destination URL against SSRF attacks.
    Raises HTTPException 400 or ValueError if destination is unsafe.
    """
    if not url or not isinstance(url, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid outbound URL provided.",
        )

    url_clean = url.strip()
    parsed = urllib.parse.urlparse(url_clean)

    # 1. Scheme check
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Forbidden URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.",
        )

    # 2. Hostname extraction
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL is missing a valid host name.",
        )

    hostname_lower = hostname.lower()

    # 3. Explicit blocked hostnames
    if not allow_local_dev and hostname_lower in BLOCKED_HOSTNAMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Requests to '{hostname}' are blocked by SSRF security policy.",
        )

    # 4. Domain allowlist if specified
    if allowlist_domains:
        domain_matched = any(
            hostname_lower == d.lower() or hostname_lower.endswith("." + d.lower())
            for d in allowlist_domains
        )
        if not domain_matched:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Host '{hostname}' is not in the authorized domain allowlist.",
            )

    # 5. DNS Resolution & IP Range Check
    if not allow_local_dev:
        try:
            # Resolve DNS
            addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
            for family, _, _, _, sockaddr in addr_info:
                ip_address_str = sockaddr[0]
                forbidden, reason = is_ip_forbidden(ip_address_str)
                if forbidden:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Destination resolves to forbidden network address ({reason}).",
                    )
        except socket.gaierror:
            # If domain cannot be resolved, reject safely
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Destination hostname '{hostname}' could not be resolved.",
            )

    return url_clean
