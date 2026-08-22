"""
TourSafe Legal Hold Service.
Manages legal holds placed on users, incidents, jurisdictions, or data types to prevent automatic or manual deletion.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pymongo import ASCENDING, DESCENDING, IndexModel

from ...core import database as db_core
from ...models.compliance import (
    DataCategory,
    LegalHold,
    LegalHoldScopeType,
    LegalHoldStatus,
)
from ..governance.audit_service import audit_service


class LegalHoldService:
    def __init__(self):
        self.collection_name = "compliance_legal_holds"

    def _get_collection(self):
        db = db_core.get_database()
        return db[self.collection_name]

    async def init_indexes(self):
        try:
            coll = self._get_collection()
            indexes = [
                IndexModel([("id", ASCENDING)], unique=True),
                IndexModel([("status", ASCENDING)]),
                IndexModel([("scope_type", ASCENDING), ("scope_id", ASCENDING)]),
                IndexModel([("placed_at", DESCENDING)]),
            ]
            await coll.create_indexes(indexes)
        except Exception as e:
            print(f"⚠️ LegalHoldService index init note: {e}")

    async def create_hold(
        self,
        title: str,
        reason: str,
        scope_type: LegalHoldScopeType,
        scope_id: str,
        placed_by: str,
        data_categories: Optional[List[DataCategory]] = None,
        date_range_start: Optional[datetime] = None,
        date_range_end: Optional[datetime] = None,
        review_date: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> LegalHold:
        hold = LegalHold(
            title=title,
            reason=reason,
            scope_type=scope_type,
            scope_id=scope_id,
            placed_by=placed_by,
            data_categories=data_categories or list(DataCategory),
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            review_date=review_date,
            notes=notes,
            status=LegalHoldStatus.ACTIVE,
        )

        coll = self._get_collection()
        doc = hold.model_dump()
        await coll.insert_one(doc)

        await audit_service.log_action(
            actor_id=placed_by,
            actor_role="admin",
            action="CREATE",
            resource_type="LEGAL_HOLD",
            resource_id=hold.id,
            after_state={"title": title, "scope_type": scope_type.value, "scope_id": scope_id, "reason": reason},
            change_reason=f"Applied legal hold: {title}",
        )

        return hold

    async def release_hold(
        self,
        hold_id: str,
        released_by: str,
        release_reason: str,
    ) -> Optional[LegalHold]:
        coll = self._get_collection()
        doc = await coll.find_one({"id": hold_id})
        if not doc:
            return None

        now = datetime.now(timezone.utc)
        update = {
            "status": LegalHoldStatus.RELEASED.value,
            "released_by": released_by,
            "released_at": now,
            "release_reason": release_reason,
            "updated_at": now,
        }

        await coll.update_one({"id": hold_id}, {"$set": update})
        updated_doc = await coll.find_one({"id": hold_id})

        await audit_service.log_action(
            actor_id=released_by,
            actor_role="admin",
            action="UPDATE",
            resource_type="LEGAL_HOLD",
            resource_id=hold_id,
            before_state={"status": doc.get("status")},
            after_state={"status": LegalHoldStatus.RELEASED.value, "release_reason": release_reason},
            change_reason=f"Released legal hold: {release_reason}",
        )

        return LegalHold.model_validate(updated_doc)

    async def get_hold(self, hold_id: str) -> Optional[LegalHold]:
        coll = self._get_collection()
        doc = await coll.find_one({"id": hold_id})
        if not doc:
            return None
        return LegalHold.model_validate(doc)

    async def list_holds(
        self,
        status: Optional[str] = None,
        scope_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[LegalHold]:
        coll = self._get_collection()
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status
        if scope_type:
            query["scope_type"] = scope_type

        cursor = coll.find(query).sort("placed_at", DESCENDING).limit(limit)
        results = []
        async for doc in cursor:
            results.append(LegalHold.model_validate(doc))
        return results

    async def is_entity_held(
        self,
        entity_id: str,
        data_category: Optional[DataCategory] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks if an entity (user_id, incident_id, etc.) is currently blocked from deletion
        by an active legal hold.
        Returns: (is_held, hold_reason)
        """
        coll = self._get_collection()
        query = {
            "status": LegalHoldStatus.ACTIVE.value,
            "$or": [
                {"scope_id": entity_id},
                {"scope_type": LegalHoldScopeType.DATA_TYPE.value, "scope_id": data_category.value if data_category else "ALL"},
            ],
        }
        hold = await coll.find_one(query)
        if hold:
            return True, f"Active Legal Hold: {hold.get('title')} (ID: {hold.get('id')})"
        return False, None


legal_hold_service = LegalHoldService()
