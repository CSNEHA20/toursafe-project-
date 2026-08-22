"""
TourSafe Responder & Unit Management Service

Coordinates responder registration, unit hierarchy, capability matrix,
strict state machine transition verification, and deterministic recommendation engine
without fabricated locations or fake routing algorithms.
"""

from datetime import datetime, timezone
import logging
import math
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from ...core import database as db_core
from ...schemas.emergency import (
    RejectionReason,
    ResponderCapability,
    ResponderCreateRequest,
    ResponderRecommendationItem,
    ResponderRecord,
    ResponderStatus,
    ResponderType,
    ResponderUnitCreateRequest,
    ResponderUnitRecord,
    ResponderUnitUpdateRequest,
    ResponderUpdateRequest,
    UnitStatus,
)
from ...schemas.realtime import RealtimeEventEnvelope, RealtimeEventType
from ...services.realtime_bus import realtime_bus


def get_database():
    return db_core.get_database()


logger = logging.getLogger("toursafe.emergency.responder")

# Strict Responder State Transition Matrix
ALLOWED_RESPONDER_TRANSITIONS: Dict[ResponderStatus, Set[ResponderStatus]] = {
    ResponderStatus.OFFLINE: {
        ResponderStatus.AVAILABLE,
        ResponderStatus.UNAVAILABLE,
    },
    ResponderStatus.AVAILABLE: {
        ResponderStatus.OFFLINE,
        ResponderStatus.UNAVAILABLE,
        ResponderStatus.ASSIGNED,
    },
    ResponderStatus.ASSIGNED: {
        ResponderStatus.RESPONDING,
        ResponderStatus.AVAILABLE,  # Rejection or authority cancellation
        ResponderStatus.OFFLINE,
    },
    ResponderStatus.RESPONDING: {
        ResponderStatus.ON_SCENE,
        ResponderStatus.AVAILABLE,  # Emergency cancellation / abort
        ResponderStatus.OFFLINE,
    },
    ResponderStatus.ON_SCENE: {
        ResponderStatus.AVAILABLE,  # Assignment completed
        ResponderStatus.OFFLINE,
    },
    ResponderStatus.UNAVAILABLE: {
        ResponderStatus.AVAILABLE,
        ResponderStatus.OFFLINE,
    },
}

# Unit State Transition Matrix
ALLOWED_UNIT_TRANSITIONS: Dict[UnitStatus, Set[UnitStatus]] = {
    UnitStatus.OFFLINE: {UnitStatus.AVAILABLE, UnitStatus.MAINTENANCE},
    UnitStatus.AVAILABLE: {UnitStatus.ASSIGNED, UnitStatus.UNAVAILABLE, UnitStatus.OFFLINE, UnitStatus.MAINTENANCE},
    UnitStatus.ASSIGNED: {UnitStatus.RESPONDING, UnitStatus.AVAILABLE, UnitStatus.OFFLINE},
    UnitStatus.RESPONDING: {UnitStatus.ON_SCENE, UnitStatus.AVAILABLE, UnitStatus.OFFLINE},
    UnitStatus.ON_SCENE: {UnitStatus.AVAILABLE, UnitStatus.OFFLINE},
    UnitStatus.UNAVAILABLE: {UnitStatus.AVAILABLE, UnitStatus.OFFLINE, UnitStatus.MAINTENANCE},
    UnitStatus.MAINTENANCE: {UnitStatus.AVAILABLE, UnitStatus.OFFLINE},
}


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes true geodesic distance in meters between two WGS84 GPS points.
    Does NOT fabricate routing paths or fake travel estimates.
    """
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class ResponderService:
    """
    Service for managing response teams, units, field operators, and capability matching.
    """

    def is_status_transition_allowed(self, current: Any, target: Any) -> bool:
        c_name = current.value if hasattr(current, "value") else str(current)
        t_name = target.value if hasattr(target, "value") else str(target)
        for state_enum, allowed_set in ALLOWED_RESPONDER_TRANSITIONS.items():
            if state_enum.value == c_name:
                return t_name in {s.value for s in allowed_set}
        return False

    def is_unit_transition_allowed(self, current: Any, target: Any) -> bool:
        c_name = current.value if hasattr(current, "value") else str(current)
        t_name = target.value if hasattr(target, "value") else str(target)
        for state_enum, allowed_set in ALLOWED_UNIT_TRANSITIONS.items():
            if state_enum.value == c_name:
                return t_name in {s.value for s in allowed_set}
        return False

    # -----------------------------------------------------------------------
    # Responder CRUD & State Operations
    # -----------------------------------------------------------------------

    async def create_responder(self, req: ResponderCreateRequest) -> ResponderRecord:
        now_iso = datetime.now(timezone.utc).isoformat()
        responder_id = f"resp_{uuid.uuid4().hex[:10]}"
        responder = ResponderRecord(
            responder_id=responder_id,
            user_id=req.user_id,
            name=req.name,
            type=req.type,
            unit_id=req.unit_id,
            status=ResponderStatus.AVAILABLE,
            capabilities=req.capabilities,
            contact_channel=req.contact_channel,
            contact_phone=req.contact_phone,
            active=True,
            created_at=now_iso,
            updated_at=now_iso,
        )
        db = get_database()
        await db.responders.insert_one(responder.model_dump())

        # If unit specified, add responder to unit members
        if req.unit_id:
            await db.responder_units.update_one(
                {"unit_id": req.unit_id},
                {"$addToSet": {"members": responder_id}, "$set": {"updated_at": now_iso}}
            )

        return responder

    async def get_responder(self, responder_id: str) -> Optional[ResponderRecord]:
        db = get_database()
        doc = await db.responders.find_one({"responder_id": responder_id})
        if not doc:
            return None
        return ResponderRecord(**doc)

    async def get_responder_by_user_id(self, user_id: str) -> Optional[ResponderRecord]:
        db = get_database()
        doc = await db.responders.find_one({"user_id": user_id})
        if not doc:
            return None
        return ResponderRecord(**doc)

    async def list_responders(
        self,
        status: Optional[ResponderStatus] = None,
        responder_type: Optional[ResponderType] = None,
        unit_id: Optional[str] = None,
        capability: Optional[str] = None,
        active_only: bool = True,
        limit: int = 50,
        skip: int = 0,
    ) -> Tuple[List[ResponderRecord], int]:
        db = get_database()
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status.value if hasattr(status, "value") else status
        if responder_type:
            query["type"] = responder_type.value if hasattr(responder_type, "value") else responder_type
        if unit_id:
            query["unit_id"] = unit_id
        if capability:
            query["capabilities"] = capability
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
        if req.contact_phone is not None:
            update_fields["contact_phone"] = req.contact_phone

        res = await db.responders.find_one_and_update(
            {"responder_id": responder_id},
            {"$set": update_fields},
            return_document=True,
        )
        if not res:
            return None
        return ResponderRecord(**res)

    async def set_responder_status(
        self,
        responder_id: str,
        target_status: ResponderStatus,
        reason: Optional[str] = None,
    ) -> ResponderRecord:
        """
        Updates responder status with strict validation against state transition rules
        and active incident assignment locks.
        """
        responder = await self.get_responder(responder_id)
        if not responder:
            raise ValueError(f"Responder '{responder_id}' not found")

        current_status = responder.status
        if current_status == target_status:
            return responder

        if not self.is_status_transition_allowed(current_status, target_status):
            raise ValueError(
                f"Invalid status transition from '{current_status.value}' to '{target_status.value}'"
            )

        # Server-side validation: Cannot become AVAILABLE while bound to an active assignment
        if target_status == ResponderStatus.AVAILABLE and responder.active_assignment_id:
            raise ValueError(
                f"Cannot set status to AVAILABLE while active assignment '{responder.active_assignment_id}' is active. Complete or release the assignment first."
            )

        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        res = await db.responders.find_one_and_update(
            {"responder_id": responder_id},
            {
                "$set": {
                    "status": target_status.value if hasattr(target_status, "value") else str(target_status),
                    "updated_at": now_iso,
                }
            },
            return_document=True,
        )
        updated_rec = ResponderRecord(**res)

        # Broadcast realtime event
        await realtime_bus.publish_event(
            event_type=RealtimeEventType.RESPONDER_STATUS_UPDATED.value,
            payload={
                "responder_id": responder_id,
                "previous_status": current_status.value if hasattr(current_status, "value") else str(current_status),
                "new_status": updated_rec.status.value if hasattr(updated_rec.status, "value") else str(updated_rec.status),
                "unit_id": updated_rec.unit_id,
                "reason": reason,
                "timestamp": now_iso,
            },
            target_role="authority",
        )
        return updated_rec

    async def assign_to_incident(
        self,
        responder_id: str,
        incident_id: str,
        assignment_id: Optional[str] = None,
    ) -> Optional[ResponderRecord]:
        """
        Atomic assignment lock to prevent race conditions.
        """
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        asgn_id = assignment_id or f"asgn_{uuid.uuid4().hex[:12]}"
        res = await db.responders.find_one_and_update(
            {
                "responder_id": responder_id,
                "active": True,
                "$or": [
                    {"status": ResponderStatus.AVAILABLE.value},
                    {"active_assignment_id": None},
                ],
            },
            {
                "$set": {
                    "status": ResponderStatus.ASSIGNED.value,
                    "assigned_incident_id": incident_id,
                    "active_assignment_id": asgn_id,
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
                    "active_assignment_id": None,
                    "updated_at": now_iso,
                }
            },
            return_document=True,
        )
        if not res:
            return None
        return ResponderRecord(**res)

    # -----------------------------------------------------------------------
    # Unit Management
    # -----------------------------------------------------------------------

    async def create_unit(self, req: ResponderUnitCreateRequest) -> ResponderUnitRecord:
        now_iso = datetime.now(timezone.utc).isoformat()
        unit_id = f"unit_{uuid.uuid4().hex[:10]}"
        unit = ResponderUnitRecord(
            unit_id=unit_id,
            name=req.name,
            type=req.type,
            status=UnitStatus.AVAILABLE,
            capabilities=req.capabilities,
            members=req.members,
            base_location=req.base_location,
            active=True,
            created_at=now_iso,
            updated_at=now_iso,
        )
        db = get_database()
        await db.responder_units.insert_one(unit.model_dump())

        # Associate members if provided
        if req.members:
            await db.responders.update_many(
                {"responder_id": {"$in": req.members}},
                {"$set": {"unit_id": unit_id, "updated_at": now_iso}}
            )

        return unit

    async def get_unit(self, unit_id: str) -> Optional[ResponderUnitRecord]:
        db = get_database()
        doc = await db.responder_units.find_one({"unit_id": unit_id})
        if not doc:
            return None
        return ResponderUnitRecord(**doc)

    async def list_units(
        self,
        status: Optional[UnitStatus] = None,
        unit_type: Optional[ResponderType] = None,
        active_only: bool = True,
        limit: int = 50,
        skip: int = 0,
    ) -> Tuple[List[ResponderUnitRecord], int]:
        db = get_database()
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status.value if hasattr(status, "value") else status
        if unit_type:
            query["type"] = unit_type.value if hasattr(unit_type, "value") else unit_type
        if active_only:
            query["active"] = True

        cursor = db.responder_units.find(query).skip(skip).limit(limit)
        items = []
        async for doc in cursor:
            items.append(ResponderUnitRecord(**doc))

        total = await db.responder_units.count_documents(query)
        return items, total

    async def update_unit(
        self,
        unit_id: str,
        req: ResponderUnitUpdateRequest,
    ) -> Optional[ResponderUnitRecord]:
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        update_fields: Dict[str, Any] = {"updated_at": now_iso}

        if req.name is not None:
            update_fields["name"] = req.name
        if req.status is not None:
            update_fields["status"] = req.status.value if hasattr(req.status, "value") else req.status
        if req.capabilities is not None:
            update_fields["capabilities"] = req.capabilities
        if req.members is not None:
            update_fields["members"] = req.members
        if req.base_location is not None:
            update_fields["base_location"] = req.base_location
        if req.active is not None:
            update_fields["active"] = req.active

        res = await db.responder_units.find_one_and_update(
            {"unit_id": unit_id},
            {"$set": update_fields},
            return_document=True,
        )
        if not res:
            return None
        return ResponderUnitRecord(**res)


class ResponderRecommendationService:
    """
    Deterministic operational recommendation engine.
    Calculates candidate eligibility, capability matching, and geodesic distances.
    CRITICAL: Does NOT perform automated dispatch. The human authority dispatcher retains complete command.
    """

    async def get_recommendations_for_incident(
        self,
        incident_lat: Optional[float] = None,
        incident_lon: Optional[float] = None,
        required_capabilities: Optional[List[str]] = None,
        target_type: Optional[ResponderType] = None,
        max_results: int = 10,
    ) -> List[ResponderRecommendationItem]:
        db = get_database()
        query: Dict[str, Any] = {"active": True}

        if target_type:
            query["type"] = target_type.value if hasattr(target_type, "value") else str(target_type)

        cursor = db.responders.find(query)
        items: List[ResponderRecommendationItem] = []
        req_caps_set = set(required_capabilities or [])

        # Pre-fetch unit names for display
        unit_docs = await db.responder_units.find({}).to_list(100)
        unit_map = {u["unit_id"]: u.get("name", "") for u in unit_docs}

        async for doc in cursor:
            rec = ResponderRecord(**doc)
            responder_caps = set(rec.capabilities)
            matched = list(req_caps_set.intersection(responder_caps))

            # Calculate geodesic distance if GPS available for both
            distance_m: Optional[float] = None
            if (
                incident_lat is not None and
                incident_lon is not None and
                rec.current_location and
                "latitude" in rec.current_location and
                "longitude" in rec.current_location
            ):
                try:
                    r_lat = float(rec.current_location["latitude"])
                    r_lon = float(rec.current_location["longitude"])
                    distance_m = round(haversine_distance_meters(incident_lat, incident_lon, r_lat, r_lon), 1)
                except Exception:
                    distance_m = None

            # Calculate freshness
            freshness = "OFFLINE" if rec.status == ResponderStatus.OFFLINE else "UNKNOWN"
            if rec.last_location_timestamp:
                try:
                    ts = datetime.fromisoformat(rec.last_location_timestamp.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - ts).total_seconds()
                    if age <= 15:
                        freshness = "LIVE"
                    elif age <= 60:
                        freshness = "RECENT"
                    elif age <= 300:
                        freshness = "STALE"
                    else:
                        freshness = "OFFLINE"
                except Exception:
                    pass

            # Deterministic scoring:
            # - AVAILABLE: +100
            # - Cap Match: +20 per matched capability
            # - Distance penalty: -1 point per 500m
            score = 0.0
            if rec.status == ResponderStatus.AVAILABLE:
                score += 100.0
            elif rec.status == ResponderStatus.ASSIGNED:
                score += 20.0
            elif rec.status == ResponderStatus.UNAVAILABLE:
                score += 0.0
            else:
                score -= 50.0

            score += len(matched) * 25.0
            if distance_m is not None:
                score = max(0.0, score - (distance_m / 500.0))

            items.append(
                ResponderRecommendationItem(
                    responder_id=rec.responder_id,
                    name=rec.name,
                    type=rec.type,
                    unit_id=rec.unit_id,
                    unit_name=unit_map.get(rec.unit_id or "", None),
                    status=rec.status,
                    capabilities=rec.capabilities,
                    matched_capabilities=matched,
                    distance_meters=distance_m,
                    location_freshness=freshness,
                    current_location=rec.current_location,
                    active_assignment_id=rec.active_assignment_id,
                    score=round(score, 2),
                )
            )

        # Sort descending by score
        items.sort(key=lambda x: x.score, reverse=True)
        return items[:max_results]


responder_service = ResponderService()
responder_recommendation_service = ResponderRecommendationService()
