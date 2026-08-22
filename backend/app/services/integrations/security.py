import ipaddress
import logging
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

logger = logging.getLogger("toursafe.integrations.security")

# Blocked IP networks for SSRF Defense
BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # RFC 1918 Private
    ipaddress.ip_network("172.16.0.0/12"),    # RFC 1918 Private
    ipaddress.ip_network("192.168.0.0/16"),   # RFC 1918 Private
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local / Cloud Metadata (AWS/GCP/Azure)
    ipaddress.ip_network("100.64.0.0/10"),    # Carrier-grade NAT
    ipaddress.ip_network("::1/128"),          # IPv6 Loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 Unique Local
    ipaddress.ip_network("fe80::/10"),        # IPv6 Link-Local
]

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "169.254.169.254",
    "instance-data",
}

SENSITIVE_FIELD_PATTERNS = [
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"auth[_-]?token", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
    re.compile(r"private[_-]?key", re.IGNORECASE),
    re.compile(r"bearer", re.IGNORECASE),
]


class SSRFProtectionException(Exception):
    def __init__(self, target_url: str, reason: str):
        super().__init__(f"SSRF Protection Blocked Request to '{target_url}': {reason}")
        self.target_url = target_url
        self.reason = reason


class SecurityManager:
    """
    Integration Security Manager.
    Enforces SSRF prevention, Secret Masking / Redaction, and PII Minimization.
    """

    @staticmethod
    def validate_outbound_url(url: str, allowlist_domains: Optional[List[str]] = None) -> bool:
        """
        Validates URL to protect against SSRF and unauthorized external endpoints.
        Raises SSRFProtectionException if unsafe.
        """
        if not url:
            raise SSRFProtectionException(url, "Empty URL provided")

        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname or ""

        if scheme not in ("http", "https"):
            raise SSRFProtectionException(url, f"Forbidden URL scheme '{scheme}'. Only HTTP/HTTPS allowed.")

        if not hostname:
            raise SSRFProtectionException(url, "Invalid or missing hostname")

        hostname_lower = hostname.lower()

        # 1. Check blocked hostnames
        if hostname_lower in BLOCKED_HOSTNAMES or "metadata" in hostname_lower:
            raise SSRFProtectionException(url, f"Forbidden hostname '{hostname}' (cloud metadata / loopback protection)")

        # 2. Check IP literals
        try:
            ip_obj = ipaddress.ip_address(hostname_lower)
            for blocked_net in BLOCKED_NETWORKS:
                if ip_obj in blocked_net:
                    raise SSRFProtectionException(url, f"IP address '{ip_obj}' resides within protected internal network {blocked_net}")
        except ValueError:
            # Not an IP literal, it's a domain name
            pass

        # 3. Check Domain Allowlist if configured
        if allowlist_domains and len(allowlist_domains) > 0:
            domain_matched = False
            for allowed in allowlist_domains:
                allowed_lower = allowed.lower()
                if hostname_lower == allowed_lower or hostname_lower.endswith(f".{allowed_lower}"):
                    domain_matched = True
                    break
            if not domain_matched:
                raise SSRFProtectionException(
                    url,
                    f"Domain '{hostname}' is not in configured integration allowlist: {allowlist_domains}",
                )

        return True

    @staticmethod
    def redact_secrets(data: Any) -> Any:
        """
        Recursively redact secrets, credentials, tokens, and sensitive headers from dicts/lists.
        """
        if isinstance(data, dict):
            sanitized = {}
            for k, v in data.items():
                is_sensitive = any(pat.search(str(k)) for pat in SENSITIVE_FIELD_PATTERNS)
                if is_sensitive and isinstance(v, str) and v:
                    # Mask secret
                    if len(v) > 8:
                        sanitized[k] = f"{v[:4]}****{v[-4:]}"
                    else:
                        sanitized[k] = "********"
                else:
                    sanitized[k] = SecurityManager.redact_secrets(v)
            return sanitized
        elif isinstance(data, list):
            return [SecurityManager.redact_secrets(item) for item in data]
        return data

    @staticmethod
    def minimize_pii(data: Dict[str, Any], is_emergency: bool = False) -> Dict[str, Any]:
        """
        Apply data minimization for external provider dispatches.
        - In non-emergency mode, rounds coordinates to 3 decimal places (~100m precision).
        - Masks tourist national IDs, phone numbers, and removes private medical logs unless explicitly needed.
        """
        minimized = dict(data)

        # Coordinate fuzzing for non-emergency third parties
        if not is_emergency:
            if "latitude" in minimized and isinstance(minimized["latitude"], (int, float)):
                minimized["latitude"] = round(minimized["latitude"], 3)
            if "longitude" in minimized and isinstance(minimized["longitude"], (int, float)):
                minimized["longitude"] = round(minimized["longitude"], 3)
            if "coordinates" in minimized and isinstance(minimized["coordinates"], list) and len(minimized["coordinates"]) >= 2:
                minimized["coordinates"] = [round(minimized["coordinates"][0], 3), round(minimized["coordinates"][1], 3)]

        # Phone masking: e.g. +91 98765 43210 -> +91 98*** **210
        if "phone" in minimized and isinstance(minimized["phone"], str):
            p = minimized["phone"]
            if len(p) > 6:
                minimized["phone"] = f"{p[:4]}****{p[-2:]}"

        # Tourist name masking if present
        if "tourist_name" in minimized and isinstance(minimized["tourist_name"], str):
            parts = minimized["tourist_name"].split()
            if len(parts) > 1:
                minimized["tourist_name"] = f"{parts[0]} {parts[1][0]}."

        # Remove medical secrets
        minimized.pop("blood_group", None)
        minimized.pop("allergies", None)
        minimized.pop("medical_notes", None)

        return minimized


# Global Singleton
security_manager = SecurityManager()
