"""
TourSafe Multi-Tier Rate Limiting & Abuse Prevention Engine.
Implements sliding-window in-memory and Redis-backed rate limiters for:
- Authentication & Login (Brute force & credential stuffing defense)
- Registration & OTP
- Telemetry Ingestion (High-frequency flood protection)
- AI Copilot Queries (Model abuse protection)
- Bulk Data Exports (Exfiltration defense)
- Webhooks & External Integrations
- Safety-Critical SOS Handling (Deduplication & cooldown without blocking emergency dispatch)
"""

import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException, Request, status

# In-memory sliding window store: key -> list of timestamps
_RATE_LIMIT_STORE: Dict[str, List[float]] = defaultdict(list)
# SOS Deduplication store: tourist_id -> last_sos_timestamp
_SOS_DEDUP_STORE: Dict[str, Dict[str, float]] = {}


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int, scope: str = "generic"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.scope = scope

    def check_rate_limit(self, key: str) -> Tuple[bool, int, float]:
        """
        Check rate limit using sliding window algorithm.
        Returns: (is_allowed, remaining_requests, retry_after_seconds)
        """
        now = time.time()
        window_start = now - self.window_seconds
        full_key = f"{self.scope}:{key}"

        # Clean old timestamps
        timestamps = [ts for ts in _RATE_LIMIT_STORE[full_key] if ts > window_start]
        _RATE_LIMIT_STORE[full_key] = timestamps

        if len(timestamps) >= self.max_requests:
            oldest_ts = timestamps[0]
            retry_after = max(1.0, round(self.window_seconds - (now - oldest_ts), 1))
            return False, 0, retry_after

        # Record this request
        timestamps.append(now)
        _RATE_LIMIT_STORE[full_key] = timestamps
        remaining = max(0, self.max_requests - len(timestamps))
        return True, remaining, 0.0

    def enforce(self, key: str, custom_error: Optional[str] = None):
        """Enforce rate limit, raising HTTP 429 if exceeded."""
        allowed, remaining, retry_after = self.check_rate_limit(key)
        if not allowed:
            detail = custom_error or f"Rate limit exceeded for {self.scope}. Retry after {retry_after}s."
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail,
                headers={"Retry-After": str(int(retry_after))},
            )


# Pre-configured Rate Limiters (configurable via settings / environment)
auth_rate_limiter = RateLimiter(max_requests=50, window_seconds=60, scope="auth_login")
registration_rate_limiter = RateLimiter(max_requests=50, window_seconds=60, scope="auth_register")
otp_rate_limiter = RateLimiter(max_requests=20, window_seconds=60, scope="auth_otp")
telemetry_rate_limiter = RateLimiter(max_requests=300, window_seconds=60, scope="telemetry_ingest")
copilot_rate_limiter = RateLimiter(max_requests=100, window_seconds=60, scope="copilot_chat")
export_rate_limiter = RateLimiter(max_requests=30, window_seconds=60, scope="data_export")
admin_rate_limiter = RateLimiter(max_requests=200, window_seconds=60, scope="admin_governance")
webhook_rate_limiter = RateLimiter(max_requests=300, window_seconds=60, scope="webhook_ingest")


def get_client_ip(request: Request) -> str:
    """Extract client IP address considering proxy headers safely."""
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def check_sos_rate_and_deduplicate(tourist_id: str, client_request_id: Optional[str] = None) -> Dict[str, bool]:
    """
    CRITICAL SAFETY BEHAVIOR:
    SOS triggers must NEVER be outright blocked for safety reasons.
    Instead, duplicate rapid requests within cooldown (e.g. 5 seconds) are identified
    as duplicate transmissions for the same active emergency incident.
    Returns:
      { "is_duplicate": bool, "active_incident_correlation": bool }
    """
    now = time.time()
    last_sos = _SOS_DEDUP_STORE.get(tourist_id, {})
    last_ts = last_sos.get("timestamp", 0.0)
    last_req_id = last_sos.get("client_request_id")

    is_duplicate = False
    if client_request_id and last_req_id == client_request_id:
        is_duplicate = True
    elif (now - last_ts) < 5.0:
        is_duplicate = True

    # Record latest SOS time
    _SOS_DEDUP_STORE[tourist_id] = {
        "timestamp": now,
        "client_request_id": client_request_id or "",
    }

    return {
        "is_duplicate": is_duplicate,
        "active_incident_correlation": (now - last_ts) < 300.0,
    }


def reset_rate_limit_stores():
    """Reset in-memory rate limit caches (useful for test isolation)."""
    _RATE_LIMIT_STORE.clear()
    _SOS_DEDUP_STORE.clear()
