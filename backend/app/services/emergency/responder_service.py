"""
TourSafe Responder Management Service

Coordinates responder registration, capability tracking, status updates,
and incident assignments without fabricated locations or fake third-party integrations.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from ...core import database as db_core


def get_database():
    return db_core.get_database()
from ...schemas.emergency import (
    ResponderCreateRequest,
    ResponderRecord,
    ResponderStatus,
    ResponderType,
    ResponderUpdateRequest,
)

logger = logging.getLogger("toursafe.emergency.responder")


class ResponderService:
    """
    Service for managing response teams, operators, and field responders.
    """

    async def create_responder(self, req: ResponderCreateRequest) -> ResponderRecord:
        now_iso = datetime.now(timezone.utc).isoformat()
        responder = ResponderRecord(
            name=req.name,
            type=req.type,
            unit_id=req.unit_id,
            status=ResponderStatus.AVAILABLE,
            capabilities=req.capabilities,
            contact_channel=req.contact_channel,
            active=True,
            created_at=now_iso,
            updated_at=now_iso,
        )
        db = get_database()
        await db.responders.insert_one(responder.model_dump())
        return responder

    async def get_responder(self, responder_id: str) -> Optional[ResponderRecord]:
        db = get_database()
        doc = await db.responders.find_one({"responder_id": responder_id})
        if not doc:
            return None
        return ResponderRecord(**doc)

    async def list_responders(
        self,
        status: Optional[ResponderStatus] = None,
        responder_type: Optional[ResponderType] = None,
        active_only: bool = True,
        limit: int = 50,
        skip: int = 0,
    ) -> TupleListResponders:
        db = get_database()
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status.value if hasattr(status, "value") else status
        if responder_type:
            query["type"] = responder_type.value if hasattr(responder_type, "value") else responder_type
        if active_only:
            query["active"] = True

        cursor = db.responders.find(query).skip(skip).limit(limit)
        items = []
        async for doc in cursor:
            items.append(ResponderRecord(**doc))

        total = await db.responders.count_documents(query)
        return items, total

    async def update_responder(
        self,
        responder_id: str,
        req: ResponderUpdateRequest,
    ) -> Optional[ResponderRecord]:
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        update_fields: Dict[str, Any] = {"updated_at": now_iso}

        if req.status is not None:
            update_fields["status"] = req.status.value if hasattr(req.status, "value") else req.status
        if req.capabilities is not None:
            update_fields["capabilities"] = req.capabilities
        if req.current_location is not None:
            update_fields["current_location"] = req.current_location
        if req.active is not None:
            update_fields["active"] = req.active
        if req.unit_id is not None:
            update_fields["unit_id"] = req.unit_id

        res = await db.responders.find_one_and_update(
            {"responder_id": responder_id},
            {"$set": update_fields},
            return_document=True,
        )
        if not res:
            return None
        return ResponderRecord(**res)

    async def assign_to_incident(
        self,
        responder_id: str,
        incident_id: str,
    ) -> Optional[ResponderRecord]:
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        res = await db.responders.find_one_and_update(
            {"responder_id": responder_id},
            {
                "$set": {
                    "status": ResponderStatus.ASSIGNED.value,
                    "assigned_incident_id": incident_id,
                    "updated_at": now_iso,
                }
            },
            return_document=True,
        )
        if not res:
            return None
        return ResponderRecord(**res)

    async def release_from_incident(self, responder_id: str) -> Optional[ResponderRecord]:
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        res = await db.responders.find_one_and_update(
            {"responder_id": responder_id},
            {
                "$set": {
                    "status": ResponderStatus.AVAILABLE.value,
                    "assigned_incident_id": None,
                    "updated_at": now_iso,
                }
            },
            return_document=True,
        )
        if not res:
            return None
        return ResponderRecord(**res)


TupleListResponders = Any
responder_service = ResponderService()
