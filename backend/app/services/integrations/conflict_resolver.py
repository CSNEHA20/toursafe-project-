import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from ...core.database import get_database
from ...schemas.integrations import ExternalStateConflict

logger = logging.getLogger("toursafe.integrations.conflict")


class ExternalConflictService:
    """
    Manages state synchronization and conflict resolution between TourSafe and external partner systems.
    Prevents silent overwriting when operational systems disagree.
    """

    def __init__(self):
        self._memory_conflicts: Dict[str, Dict[str, Any]] = {}

    async def detect_or_record_conflict(
        self,
        toursafe_incident_id: str,
        external_system: str,
        external_incident_id: str,
        toursafe_status: str,
        external_status: str,
    ) -> Optional[ExternalStateConflict]:
        # If statuses match or are logically equivalent, no conflict
        norm_ts = toursafe_status.upper()
        norm_ext = external_status.upper()

        if norm_ts == norm_ext:
            return None

        # Check existing unresolved conflicts
        for conf in self._memory_conflicts.values():
            if (
                conf.get("toursafe_incident_id") == toursafe_incident_id
                and conf.get("external_system") == external_system
                and not conf.get("resolved")
            ):
                return ExternalStateConflict(**conf)

        conflict_id = f"conf_{uuid.uuid4().hex[:12]}"
        conflict = ExternalStateConflict(
            conflict_id=conflict_id,
            toursafe_incident_id=toursafe_incident_id,
            external_system=external_system,
            external_incident_id=external_incident_id,
            toursafe_status=toursafe_status,
            external_status=external_status,
            detected_at=datetime.now(timezone.utc).isoformat(),
            resolved=False,
        )

        doc = conflict.model_dump() if hasattr(conflict, "model_dump") else conflict.dict()
        doc["_id"] = conflict_id
        self._memory_conflicts[conflict_id] = doc

        try:
            db = get_database()
            if db is not None:
                await asyncio.wait_for(db["integration_state_conflicts"].insert_one(doc), timeout=0.5)
        except Exception as e:
            logger.debug("ExternalConflictService: MongoDB insert notice: %s", e)

        logger.warning(
            "ExternalConflictService: CONFLICT DETECTED [%s] for incident %s (TourSafe: %s vs %s: %s)",
            conflict_id,
            toursafe_incident_id,
            toursafe_status,
            external_system,
            external_status,
        )
        return conflict

    async def list_conflicts(self, resolved: Optional[bool] = None, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            db = get_database()
            if db is not None:
                query = {}
                if resolved is not None:
                    query["resolved"] = resolved
                cursor = db["integration_state_conflicts"].find(query).sort("detected_at", -1).limit(limit)
                return await cursor.to_list(length=limit)
        except Exception as e:
            logger.warning("ExternalConflictService: DB query fallback: %s", e)

        conflicts = list(self._memory_conflicts.values())
        if resolved is not None:
            conflicts = [c for c in conflicts if c.get("resolved") == resolved]
        conflicts.sort(key=lambda x: x.get("detected_at", ""), reverse=True)
        return conflicts[:limit]

    async def resolve_conflict(
        self,
        conflict_id: str,
        policy: str,  # TOURSAFE_WINS, EXTERNAL_WINS, MANUAL_OVERRIDE
        chosen_status: str,
        actor_id: str,
    ) -> Optional[ExternalStateConflict]:
        now = datetime.now(timezone.utc).isoformat()
        if conflict_id in self._memory_conflicts:
            self._memory_conflicts[conflict_id]["resolved"] = True
            self._memory_conflicts[conflict_id]["resolution_policy"] = policy
            self._memory_conflicts[conflict_id]["resolved_status"] = chosen_status
            self._memory_conflicts[conflict_id]["resolved_by"] = actor_id
            self._memory_conflicts[conflict_id]["resolved_at"] = now

        try:
            db = get_database()
            if db is not None:
                await db["integration_state_conflicts"].update_one(
                    {"conflict_id": conflict_id},
                    {
                        "$set": {
                            "resolved": True,
                            "resolution_policy": policy,
                            "resolved_status": chosen_status,
                            "resolved_by": actor_id,
                            "resolved_at": now,
                        }
                    },
                )
        except Exception as e:
            logger.warning("ExternalConflictService: DB resolve error: %s", e)

        record = self._memory_conflicts.get(conflict_id)
        if record:
            return ExternalStateConflict(**record)
        return None


# Global Singleton
conflict_service = ExternalConflictService()
