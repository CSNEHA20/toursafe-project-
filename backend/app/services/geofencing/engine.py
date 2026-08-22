"""
TourSafe - Real-Time Geo-Fencing Engine

Coordinates:
- GPS location stream consumption from LocationService
- Spatial candidate zone queries (2dsphere index)
- Precise GeoJSON point-in-polygon & boundary distance evaluations
- Multi-zone concurrent containment & risk derivation
- Hysteresis & temporal jitter damping
- Actual timestamp-based dwell tracking & threshold alerts
- Active state caching in Redis (TTL + in-memory fallback)
- Persistent transition auditing in MongoDB 'zone_transitions'
- Realtime event dispatch to tourist and authority WebSocket channels
- Non-destructive stale GPS handling
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ...core.redis import get_redis_client
from .events import geofence_event_publisher
from .geometry import evaluate_point_containment
from .repository import geofence_repository
from .state import GeofenceStateMachine, ZoneStateContext
from .types import (
    ActiveZoneMembership,
    GeofenceDiagnostics,
    MembershipConfidence,
    TouristGeofenceSnapshot,
    ZoneMembershipState,
    ZoneTransitionRecord,
)
from ..safety import safety_orchestrator, SafetySignalFactory

logger = logging.getLogger("toursafe.geofencing.engine")

REDIS_GEOFENCE_TTL_SECONDS = 120  # 2 minutes TTL matching GPS live cache
RISK_PRIORITY = {"critical": 4, "high": 3, "medium": 2, "low": 1}
ZONE_TYPE_PRIORITY = {"restricted": 3, "warning": 2, "safe": 1}

# In-memory store for active geofence state fallback when Redis is offline
_memory_active_geofence: Dict[str, Tuple[Dict[str, Dict[str, Any]], float]] = {}
# In-memory state context tracking for jitter sample counting
_tourist_state_contexts: Dict[str, Dict[str, ZoneStateContext]] = {}
# Last diagnostic snapshot cache
_last_diagnostics: Dict[str, GeofenceDiagnostics] = {}


class GeofenceEngine:
    """
    Central real-time geofencing engine for TourSafe.
    """

    @staticmethod
    def _redis_key(tourist_id: str) -> str:
        return f"toursafe:geofence:active:{tourist_id}"

    async def get_active_memberships(self, tourist_id: str) -> Dict[str, ActiveZoneMembership]:
        """
        Retrieves current active zone memberships for a tourist from Redis / in-memory cache.
        """
        redis = await get_redis_client()
        raw = None
        if redis is not None:
            try:
                raw = await redis.get(self._redis_key(tourist_id))
            except Exception as e:
                logger.warning("Redis geofence read error: %s", e)

        # In-memory fallback
        if not raw and tourist_id in _memory_active_geofence:
            cached_dict, expire_at = _memory_active_geofence[tourist_id]
            if time.time() <= expire_at:
                return {zid: ActiveZoneMembership(**data) for zid, data in cached_dict.items()}
            else:
                _memory_active_geofence.pop(tourist_id, None)

        if raw:
            try:
                data = json.loads(raw)
                return {zid: ActiveZoneMembership(**m) for zid, m in data.items()}
            except Exception as e:
                logger.error("Error deserializing active geofence memberships: %s", e)

        return {}

    async def save_active_memberships(
        self,
        tourist_id: str,
        memberships: Dict[str, ActiveZoneMembership],
    ) -> None:
        """
        Saves current active memberships to Redis with TTL and in-memory fallback.
        """
        serializable = {zid: m.model_dump() for zid, m in memberships.items()}
        redis = await get_redis_client()
        if redis is not None:
            try:
                if serializable:
                    await redis.set(
                        self._redis_key(tourist_id),
                        json.dumps(serializable),
                        ex=REDIS_GEOFENCE_TTL_SECONDS,
                    )
                else:
                    await redis.delete(self._redis_key(tourist_id))
            except Exception as e:
                logger.warning("Redis geofence write error: %s", e)
                _memory_active_geofence[tourist_id] = (serializable, time.time() + REDIS_GEOFENCE_TTL_SECONDS)
        else:
            _memory_active_geofence[tourist_id] = (serializable, time.time() + REDIS_GEOFENCE_TTL_SECONDS)

    async def process_location_sample(
        self,
        tourist_id: str,
        user_id: str,
        location_sample: Any,
    ) -> TouristGeofenceSnapshot:
        """
        Authoritative pipeline consuming a single GPS sample:
        1. Spatial Candidate Retrieval
        2. Exact GeoJSON containment & boundary distance
        3. Hysteresis State Machine Evaluation
        4. Realtime Event Emission & MongoDB Transition Logging
        5. Redis Active State Persistence
        """
        start_time = time.perf_counter()

        lat = getattr(location_sample, "latitude", 0.0)
        lon = getattr(location_sample, "longitude", 0.0)
        acc = getattr(location_sample, "accuracy", 10.0) or 10.0
        ts = getattr(location_sample, "timestamp", None) or datetime.now(timezone.utc).isoformat()
        session_id = getattr(location_sample, "session_id", None)

        # 1. Retrieve Candidate Zones via 2dsphere spatial indexing
        candidate_zones = await geofence_repository.find_candidate_zones(
            longitude=lon,
            latitude=lat,
            buffer_meters=max(500.0, acc * 3.0),
        )

        # 2. Retrieve existing active memberships
        active_memberships = await self.get_active_memberships(tourist_id)

        # Initialize tourist state contexts if missing
        if tourist_id not in _tourist_state_contexts:
            _tourist_state_contexts[tourist_id] = {}
        tourist_ctxs = _tourist_state_contexts[tourist_id]

        candidate_zone_ids = set()
        evaluated_zones = list(candidate_zones)

        # Check if any previously active zones are missing from candidate query (e.g. moved away)
        for zid, active_mem in active_memberships.items():
            if not any((z.get("zone_id") or z.get("id")) == zid for z in evaluated_zones):
                # Retrieve zone doc to evaluate exit
                db = geofence_repository.get_all_active_zones()
                # If zone was active, include it for exit evaluation
                evaluated_zones.append({
                    "zone_id": zid,
                    "id": zid,
                    "name": active_mem.name,
                    "zone_type": active_mem.zone_type,
                    "risk_level": active_mem.risk_level,
                    "properties": active_mem.properties,
                    "boundary": {"type": "Polygon", "coordinates": []},  # empty will evaluate outside
                })

        updated_active_memberships: Dict[str, ActiveZoneMembership] = {}
        last_event_emitted: Optional[Dict[str, Any]] = None

        # 3. Evaluate each candidate zone
        for zone in evaluated_zones:
            zid = zone.get("zone_id") or zone.get("id") or "unknown_zone"
            candidate_zone_ids.add(zid)
            boundary = zone.get("boundary", {})

            if zid not in tourist_ctxs:
                tourist_ctxs[zid] = ZoneStateContext(zone_id=zid)
            state_ctx = tourist_ctxs[zid]

            # Exact GeoJSON Point-in-Polygon & Boundary Distance
            containment = evaluate_point_containment(
                latitude=lat,
                longitude=lon,
                accuracy_meters=acc,
                boundary_geojson=boundary,
            )

            existing_membership = active_memberships.get(zid)

            # Evaluate state machine transition with hysteresis & dwell tracking
            new_state, event_type, new_membership = GeofenceStateMachine.evaluate_transition(
                tourist_id=tourist_id,
                zone=zone,
                containment=containment,
                sample_timestamp=ts,
                existing_membership=existing_membership,
                state_ctx=state_ctx,
            )

            # 4. If transition event triggered -> log to MongoDB and emit realtime event
            if event_type:
                dwell_sec = None
                if event_type == "zone.exited" and existing_membership:
                    t_entry = GeofenceStateMachine.parse_iso_timestamp(existing_membership.entered_at)
                    t_exit = GeofenceStateMachine.parse_iso_timestamp(ts)
                    dwell_sec = max(0.0, (t_exit - t_entry).total_seconds())

                # Create and persist immutable transition record
                transition_record = ZoneTransitionRecord(
                    tourist_id=tourist_id,
                    user_id=user_id,
                    zone_id=zid,
                    zone_name=zone.get("name", zid),
                    zone_type=zone.get("zone_type", "safe"),
                    risk_level=zone.get("risk_level", "low"),
                    session_id=session_id,
                    event_type=event_type,
                    from_state=existing_membership.state if existing_membership else "outside",
                    to_state=new_state.value,
                    timestamp=ts,
                    latitude=lat,
                    longitude=lon,
                    location={"type": "Point", "coordinates": [lon, lat]},
                    accuracy=containment.accuracy_meters,
                    confidence_score=containment.confidence_score,
                    confidence_level=containment.confidence_level.value,
                    boundary_distance_meters=containment.distance_to_boundary_meters,
                    dwell_duration_seconds=dwell_sec,
                    geometry_version=str(zone.get("updated_at", "")),
                )
                await geofence_repository.record_transition(transition_record)

                # Broadcast realtime event envelope
                envelope = await geofence_event_publisher.publish_zone_event(
                    event_type=event_type,
                    tourist_id=tourist_id,
                    user_id=user_id,
                    zone=zone,
                    location_sample=location_sample,
                    containment=containment,
                    membership=new_membership or existing_membership,
                    dwell_duration_seconds=dwell_sec,
                )
                if envelope and isinstance(getattr(envelope, "payload", None), dict):
                    last_event_emitted = envelope.payload

            # 5. Maintain active memberships
            if new_membership and new_state in (
                ZoneMembershipState.INSIDE,
                ZoneMembershipState.ENTER_CANDIDATE,
                ZoneMembershipState.UNCERTAIN,
                ZoneMembershipState.EXIT_CANDIDATE,
            ):
                updated_active_memberships[zid] = new_membership

        # 6. Save updated active state to Redis
        await self.save_active_memberships(tourist_id, updated_active_memberships)

        # 7. Derive multi-zone aggregate properties
        active_list = list(updated_active_memberships.values())
        highest_risk = "low"
        primary_type = "safe"

        for m in active_list:
            if RISK_PRIORITY.get(m.risk_level, 0) > RISK_PRIORITY.get(highest_risk, 0):
                highest_risk = m.risk_level
            if ZONE_TYPE_PRIORITY.get(m.zone_type, 0) > ZONE_TYPE_PRIORITY.get(primary_type, 0):
                primary_type = m.zone_type

        snapshot = TouristGeofenceSnapshot(
            tourist_id=tourist_id,
            active_zones=active_list,
            highest_risk_level=highest_risk,
            primary_zone_type=primary_type,
            is_stale=False,
            last_gps_timestamp=ts,
            total_active_zones=len(active_list),
        )

        # Ingest Geofence signals to Safety Orchestration Engine (Prompt 11)
        try:
            if active_list:
                for m in active_list:
                    dwell_dur = None
                    if m.entered_at:
                        t_ent = GeofenceStateMachine.parse_iso_timestamp(m.entered_at)
                        t_curr = GeofenceStateMachine.parse_iso_timestamp(ts)
                        dwell_dur = max(0.0, (t_curr - t_ent).total_seconds())

                    geo_sig = SafetySignalFactory.create_geofence_signal(
                        tourist_id=tourist_id,
                        session_id=session_id,
                        zone_id=m.zone_id,
                        zone_name=m.name,
                        zone_type=m.zone_type,
                        risk_level=m.risk_level,
                        membership_state=m.state.value if hasattr(m.state, "value") else str(m.state),
                        dwell_duration_seconds=dwell_dur,
                        confidence_score=1.0 if m.confidence == MembershipConfidence.HIGH else 0.7,
                        timestamp=ts,
                    )
                    await safety_orchestrator.ingest_signal(geo_sig, user_id=user_id)
        except Exception as se_err:
            logger.error("Safety engine geofence ingest error for tourist %s: %s", tourist_id, se_err)

        # 8. Record Diagnostics
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        _last_diagnostics[tourist_id] = GeofenceDiagnostics(
            tourist_id=tourist_id,
            current_coordinates={"latitude": lat, "longitude": lon},
            gps_accuracy_meters=acc,
            gps_timestamp=ts,
            gps_freshness_seconds=0.0,
            candidate_zones_count=len(candidate_zones),
            candidate_zones=[
                {
                    "zone_id": z.get("zone_id") or z.get("id"),
                    "name": z.get("name"),
                    "risk_level": z.get("risk_level"),
                    "zone_type": z.get("zone_type"),
                }
                for z in candidate_zones
            ],
            active_memberships=active_list,
            highest_risk_level=highest_risk,
            last_transition_event=last_event_emitted,
            processing_latency_ms=round(elapsed_ms, 2),
            engine_status="operational",
        )

        return snapshot

    async def mark_tourist_stale(self, tourist_id: str) -> None:
        """
        Handles stale GPS: marks all active memberships for the tourist as STALE in Redis
        and broadcasts 'zone.membership.stale' without fabricating a zone exit.
        """
        active_memberships = await self.get_active_memberships(tourist_id)
        if not active_memberships:
            return

        now_utc = datetime.now(timezone.utc).isoformat()
        updated_memberships = {}

        for zid, mem in active_memberships.items():
            updated = mem.model_copy()
            updated.state = ZoneMembershipState.STALE
            updated_memberships[zid] = updated

            # Emit stale event
            await geofence_event_publisher.publish_zone_event(
                event_type="zone.membership.stale",
                tourist_id=tourist_id,
                user_id="",
                zone={"zone_id": zid, "name": mem.name, "zone_type": mem.zone_type, "risk_level": mem.risk_level},
                location_sample=type("Sample", (), {"latitude": 0.0, "longitude": 0.0, "accuracy": mem.accuracy_meters, "timestamp": now_utc, "session_id": None})(),
                containment=evaluate_point_containment(0.0, 0.0, mem.accuracy_meters, {"type": "Polygon", "coordinates": []}),
                membership=updated,
            )

        await self.save_active_memberships(tourist_id, updated_memberships)

    async def get_tourist_snapshot(self, tourist_id: str) -> TouristGeofenceSnapshot:
        """
        Get aggregated current geofence status for tourist.
        """
        active_memberships = await self.get_active_memberships(tourist_id)
        active_list = list(active_memberships.values())

        highest_risk = "low"
        primary_type = "safe"
        last_ts = None
        is_stale = False

        for m in active_list:
            if RISK_PRIORITY.get(m.risk_level, 0) > RISK_PRIORITY.get(highest_risk, 0):
                highest_risk = m.risk_level
            if ZONE_TYPE_PRIORITY.get(m.zone_type, 0) > ZONE_TYPE_PRIORITY.get(primary_type, 0):
                primary_type = m.zone_type
            if m.last_location_timestamp:
                last_ts = m.last_location_timestamp
            if m.state == ZoneMembershipState.STALE:
                is_stale = True

        return TouristGeofenceSnapshot(
            tourist_id=tourist_id,
            active_zones=active_list,
            highest_risk_level=highest_risk,
            primary_zone_type=primary_type,
            is_stale=is_stale,
            last_gps_timestamp=last_ts,
            total_active_zones=len(active_list),
        )

    def get_diagnostics(self, tourist_id: str) -> Optional[GeofenceDiagnostics]:
        """
        Returns development diagnostics for a tourist.
        """
        return _last_diagnostics.get(tourist_id)


geofence_engine = GeofenceEngine()
