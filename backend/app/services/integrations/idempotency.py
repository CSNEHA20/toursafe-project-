import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("toursafe.integrations.idempotency")


class IdempotencyManager:
    """
    Idempotency Manager for outbound integration requests and inbound webhook events.
    Caches idempotency keys with payload digests to prevent duplicate side effects.
    """

    def __init__(self, default_ttl_seconds: int = 86400):
        self.default_ttl_seconds = default_ttl_seconds
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def compute_payload_hash(payload: Any) -> str:
        if payload is None:
            return ""
        if isinstance(payload, bytes):
            return hashlib.sha256(payload).hexdigest()
        if isinstance(payload, str):
            return hashlib.sha256(payload.encode("utf-8")).hexdigest()
        try:
            serialized = json.dumps(payload, sort_keys=True, default=str)
            return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        except Exception:
            return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()

    async def check_or_record(
        self,
        idempotency_key: str,
        payload: Optional[Any] = None,
        ttl_seconds: Optional[int] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Returns (is_duplicate, cached_response_if_any).
        If not duplicate, records the key in 'IN_FLIGHT' status.
        """
        if not idempotency_key:
            return False, None

        payload_hash = self.compute_payload_hash(payload)
        now = datetime.now(timezone.utc).timestamp()
        ttl = ttl_seconds or self.default_ttl_seconds

        entry = self._memory_cache.get(idempotency_key)
        if entry:
            # Check expiry
            if now > entry.get("expires_at", 0):
                del self._memory_cache[idempotency_key]
            else:
                # Key already exists
                logger.warning("IdempotencyManager: Duplicate detected for key %s", idempotency_key)
                return True, entry.get("response")

        # Record new key
        self._memory_cache[idempotency_key] = {
            "payload_hash": payload_hash,
            "created_at": now,
            "expires_at": now + ttl,
            "status": "IN_FLIGHT",
            "response": None,
        }
        return False, None

    async def store_response(self, idempotency_key: str, response: Dict[str, Any]) -> None:
        """Stores execution response against idempotency key for replay."""
        if not idempotency_key:
            return
        if idempotency_key in self._memory_cache:
            self._memory_cache[idempotency_key]["status"] = "COMPLETED"
            self._memory_cache[idempotency_key]["response"] = response

    def clear(self) -> None:
        self._memory_cache.clear()


# Global Singleton
idempotency_manager = IdempotencyManager()
