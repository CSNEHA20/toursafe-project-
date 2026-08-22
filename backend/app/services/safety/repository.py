"""
TourSafe MongoDB Repository for Safety Decisions and Incidents

Provides immutable audit persistence and indexed retrieval for:
- safety_decisions (Collection)
- safety_incidents (Collection)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ...core.database import get_database
from ...schemas.safety import IncidentRecord, IncidentStatus, SafetyDecision

logger = logging.getLogger("toursafe.safety.repository")


class SafetyRepository:
    """
    Handles MongoDB storage and retrieval for safety decisions and incidents.
    """

    async def init_indexes(self) -> None:
        """Initializes compound and single-field indexes for optimal audit querying."""
        try:
            db = get_database()
            # Index for decisions
            await db.safety_decisions.create_index([("tourist_id", 1), ("timestamp", -1)])
            await db.safety_decisions.create_index([("decision_id", 1)], unique=True)
            await db.safety_decisions.create_index([("state", 1), ("timestamp", -1)])

            # Index for incidents
            await db.safety_incidents.create_index([("incident_id", 1)], unique=True)
            await db.safety_incidents.create_index([("tourist_id", 1), ("status", 1)])
            await db.safety_incidents.create_index([("status", 1), ("started_at", -1)])
            logger.info("✅ Safety MongoDB indexes initialized successfully")
        except Exception as e:
            logger.warning("Safety MongoDB index initialization note: %s", e)

    async def record_decision(self, decision: SafetyDecision) -> None:
        """Appends an immutable safety decision record to MongoDB."""
        try:
            db = get_database()
            doc = decision.model_dump()
            await db.safety_decisions.insert_one(doc)
        except Exception as e:
            logger.error("Failed to insert safety decision to MongoDB: %s", e)

    async def upsert_incident(self, incident: IncidentRecord) -> None:
        """Upserts an incident record into MongoDB."""
        try:
            db = get_database()
            doc = incident.model_dump()
            await db.safety_incidents.update_one(
                {"incident_id": incident.incident_id},
                {"$set": doc},
                upsert=True,
            )
        except Exception as e:
            logger.error("Failed to upsert incident record to MongoDB: %s", e)

    async def get_active_incident(self, tourist_id: str) -> Optional[IncidentRecord]:
        """Finds any non-terminal incident for the tourist."""
        try:
            db = get_database()
            doc = await db.safety_incidents.find_one(
                {
                    "tourist_id": tourist_id,
                    "status": {"$in": [IncidentStatus.OPEN.value, IncidentStatus.ACKNOWLEDGED.value, IncidentStatus.MONITORING.value]},
                },
                sort=[("started_at", -1)],
            )
            if doc:
                doc.pop("_id", None)
                return IncidentRecord(**doc)
        except Exception as e:
            logger.error("Failed to get active incident: %s", e)
        return None

    async def get_incident_by_id(self, incident_id: str) -> Optional[IncidentRecord]:
        """Finds an incident by its unique ID."""
        try:
            db = get_database()
            doc = await db.safety_incidents.find_one({"incident_id": incident_id})
            if doc:
                doc.pop("_id", None)
                return IncidentRecord(**doc)
        except Exception as e:
            logger.error("Failed to fetch incident %s: %s", incident_id, e)
        return None

    async def list_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        tourist_id: Optional[str] = None,
        limit: int = 50,
        page: int = 1,
    ) -> Tuple[List[IncidentRecord], int]:
        """Lists incidents with pagination and filtering."""
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status
        if severity:
            query["severity"] = severity
        if tourist_id:
            query["tourist_id"] = tourist_id

        try:
            db = get_database()
            skip = max(0, (page - 1) * limit)
            total = await db.safety_incidents.count_documents(query)
            cursor = db.safety_incidents.find(query).sort("started_at", -1).skip(skip).limit(limit)

            items = []
            async for doc in cursor:
                doc.pop("_id", None)
                items.append(IncidentRecord(**doc))
            return items, total
        except Exception as e:
            logger.error("Failed to list incidents: %s", e)
            return [], 0

    async def get_decision_history(
        self,
        tourist_id: str,
        limit: int = 100,
        skip: int = 0,
    ) -> Tuple[List[SafetyDecision], int]:
        """Fetches historical immutable decisions for a tourist."""
        query = {"tourist_id": tourist_id}
        try:
            db = get_database()
            total = await db.safety_decisions.count_documents(query)
            cursor = db.safety_decisions.find(query).sort("timestamp", -1).skip(skip).limit(limit)

            items = []
            async for doc in cursor:
                doc.pop("_id", None)
                items.append(SafetyDecision(**doc))
            return items, total
        except Exception as e:
            logger.error("Failed to fetch decision history for %s: %s", tourist_id, e)
            return [], 0


safety_repository = SafetyRepository()
