"""
TourSafe Security Event Monitoring & Alerting Pipeline.
Captures and aggregates security-relevant telemetry:
- Authentication failures & brute-force blocks
- Refresh token reuse & anomaly detections
- Authorization & IDOR violations
- Injection attempts (NoSQL, XSS, Path Traversal, SSRF)
- GPS spoofing & Telemetry replay events
- Administrative privilege modifications
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pymongo import ASCENDING, DESCENDING, IndexModel

from ...core import database as db_core

logger = logging.getLogger("toursafe.security.events")

# In-memory buffer for fast retrieval during testing/runtime
_SECURITY_EVENTS_LOG: List[Dict[str, Any]] = []


class SecurityEventService:
    def __init__(self):
        self.collection_name = "security_events"

    def _get_collection(self):
        return db_core.get_database()[self.collection_name]

    async def init_indexes(self):
        """Initialize indexes for security event queries."""
        try:
            coll = self._get_collection()
            await coll.create_indexes([
                IndexModel([("event_id", ASCENDING)], unique=True),
                IndexModel([("event_type", ASCENDING)]),
                IndexModel([("severity", ASCENDING)]),
                IndexModel([("timestamp", DESCENDING)]),
                IndexModel([("actor_id", ASCENDING)]),
                IndexModel([("client_ip", ASCENDING)]),
            ])
        except Exception as e:
            logger.debug("Security events index note: %s", e)

    async def record_event(
        self,
        event_type: str,
        severity: str = "MEDIUM",
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        client_ip: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a security event into audit stream and database."""
        event_record = {
            "event_id": f"sec_{uuid.uuid4().hex[:12]}",
            "event_type": event_type,
            "severity": severity.upper(),
            "actor_id": actor_id or "anonymous",
            "actor_role": actor_role or "unknown",
            "client_ip": client_ip or "127.0.0.1",
            "resource": resource or "",
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        _SECURITY_EVENTS_LOG.append(event_record)
        # Keep in-memory buffer manageable
        if len(_SECURITY_EVENTS_LOG) > 1000:
            _SECURITY_EVENTS_LOG.pop(0)

        logger.warning(
            "SECURITY EVENT [%s] severity=%s actor=%s ip=%s: %s",
            event_type,
            severity,
            actor_id,
            client_ip,
            details,
        )

        try:
            coll = self._get_collection()
            await coll.insert_one(event_record)
        except Exception as e:
            logger.debug("MongoDB security event persistence note: %s", e)

        return event_record

    async def get_security_metrics(self) -> Dict[str, Any]:
        """Aggregate security overview metrics."""
        events = list(_SECURITY_EVENTS_LOG)
        total_events = len(events)
        failed_logins = sum(1 for e in events if e.get("event_type") == "auth.login.failed")
        token_reuse = sum(1 for e in events if e.get("event_type") == "auth.token.reuse_detected")
        injection_attempts = sum(1 for e in events if "injection" in e.get("event_type", ""))
        ssrf_blocks = sum(1 for e in events if e.get("event_type") == "ssrf.blocked")
        permission_denials = sum(1 for e in events if e.get("event_type") == "authz.permission_denied")

        return {
            "total_security_events": total_events,
            "failed_logins_recorded": failed_logins,
            "token_reuse_events": token_reuse,
            "injection_attempts_blocked": injection_attempts,
            "ssrf_destinations_blocked": ssrf_blocks,
            "permission_denials": permission_denials,
            "recent_events": events[-10:][::-1],
        }

    async def query_events(
        self,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Query security events with filtering."""
        filtered = [
            e for e in _SECURITY_EVENTS_LOG
            if (not event_type or e.get("event_type") == event_type)
            and (not severity or e.get("severity") == severity.upper())
        ]
        return filtered[-limit:][::-1]


security_event_service = SecurityEventService()
