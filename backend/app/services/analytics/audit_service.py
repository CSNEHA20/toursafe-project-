"""
TourSafe Analytics Audit Service (Prompt 26)

Maintains an immutable audit log of analytical data exports, forecasting queries,
configuration updates, and operator alert acknowledgements.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from ...core import database as db_core
from ...schemas.analytics import AnalyticsAuditLogEntry

logger = logging.getLogger("toursafe.analytics.audit")


class AnalyticsAuditService:
    """
    Records and queries analytical audit trail records.
    """

    def _get_db(self):
        return db_core.get_database()

    async def log_action(
        self,
        action: str,
        user_id: str,
        role: str,
        jurisdiction_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        db = self._get_db()
        entry_id = f"aud_{uuid.uuid4().hex[:10]}"
        entry = AnalyticsAuditLogEntry(
            id=entry_id,
            action=action,
            user_id=user_id,
            role=role,
            jurisdiction_id=jurisdiction_id,
            details=details or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        try:
            await db.analytics_audit_logs.insert_one(entry.model_dump())
        except Exception as e:
            logger.warning("Failed to record analytics audit log: %s", e)
        return entry_id

    async def get_audit_logs(
        self,
        jurisdiction_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[AnalyticsAuditLogEntry]:
        db = self._get_db()
        q: Dict[str, Any] = {}
        if jurisdiction_id:
            q["jurisdiction_id"] = jurisdiction_id

        cursor = db.analytics_audit_logs.find(q).sort("timestamp", -1).limit(limit)
        logs: List[AnalyticsAuditLogEntry] = []
        async for doc in cursor:
            logs.append(AnalyticsAuditLogEntry(**doc))
        return logs


analytics_audit_service = AnalyticsAuditService()
