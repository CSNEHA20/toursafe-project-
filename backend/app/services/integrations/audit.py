import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from ...core.database import get_database
from ...schemas.integrations import IntegrationAuditEntry, IntegrationType
from .security import security_manager

logger = logging.getLogger("toursafe.integrations.audit")


class IntegrationAuditService:
    """
    Integration Audit Service.
    Persists structured, sanitized records of all integration configuration changes,
    provider switches, manual retries, and high-value external dispatches.
    """

    def __init__(self):
        self._memory_logs: List[Dict[str, Any]] = []

    async def log_action(
        self,
        action: str,
        actor_id: str,
        actor_role: str,
        correlation_id: Optional[str] = None,
        integration_id: Optional[str] = None,
        provider_name: Optional[str] = None,
        integration_type: Optional[IntegrationType] = None,
        status: str = "SUCCESS",
        latency_ms: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> IntegrationAuditEntry:
        audit_id = f"aud_int_{uuid.uuid4().hex[:12]}"
        corr_id = correlation_id or f"corr_{uuid.uuid4().hex[:10]}"
        sanitized_details = security_manager.redact_secrets(details or {})

        entry = IntegrationAuditEntry(
            audit_id=audit_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            integration_id=integration_id,
            provider_name=provider_name,
            integration_type=integration_type,
            actor_id=actor_id,
            actor_role=actor_role,
            correlation_id=corr_id,
            status=status,
            latency_ms=latency_ms,
            details=sanitized_details,
        )

        doc = entry.model_dump() if hasattr(entry, "model_dump") else entry.dict()
        doc["_id"] = audit_id

        # In-memory buffer
        self._memory_logs.append(doc)
        if len(self._memory_logs) > 500:
            self._memory_logs.pop(0)

        # MongoDB persistence
        try:
            db = get_database()
            if db is not None:
                await asyncio.wait_for(db["integration_audit_logs"].insert_one(doc), timeout=0.5)
        except Exception as e:
            logger.debug("IntegrationAuditService: MongoDB insert notice: %s", e)

        logger.info(
            "IntegrationAudit: [%s] action=%s provider=%s status=%s actor=%s",
            audit_id,
            action,
            provider_name or "N/A",
            status,
            actor_id,
        )
        return entry

    async def get_logs(
        self,
        integration_id: Optional[str] = None,
        provider_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        try:
            db = get_database()
            if db is not None:
                query = {}
                if integration_id:
                    query["integration_id"] = integration_id
                if provider_name:
                    query["provider_name"] = provider_name
                cursor = db["integration_audit_logs"].find(query).sort("timestamp", -1).limit(limit)
                return await cursor.to_list(length=limit)
        except Exception as e:
            logger.warning("IntegrationAuditService: Failed to query MongoDB logs, returning memory logs: %s", e)

        filtered = [
            l for l in reversed(self._memory_logs)
            if (not integration_id or l.get("integration_id") == integration_id)
            and (not provider_name or l.get("provider_name") == provider_name)
        ]
        return filtered[:limit]


# Global Singleton
integration_audit_service = IntegrationAuditService()
