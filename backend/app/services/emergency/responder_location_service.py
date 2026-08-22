"""
TourSafe Responder Location Service

Tracks real GPS coordinates for authenticated field responders, maintains
high-performance live Redis cache (120s TTL), persists durable location history in MongoDB,
calculates actual location staleness, and broadcasts controlled realtime events.
Zero fake locations, zero fabricated routes.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from ...core import database as db_core
from ...core.redis import get_redis_client
from ...schemas.emergency import (
    ResponderLocationUpdateRequest,
    ResponderRecord,
    ResponderStatus,
)
from ...schemas.realtime import RealtimeEventEnvelope, RealtimeEventType
from ...services.realtime_bus import realtime_bus


def get_database():
    return db_core.get_database()


logger = logging.getLogger("toursafe.emergency.responder_location")

# Configuration constants
REDIS_RESPONDER_LOCATION_TTL = 120  # seconds
LIVE_THRESHOLD_SECONDS = 15.0
RECENT_THRESHOLD_SECONDS = 60.0
STALE_THRESHOLD_SECONDS = 300.0
ACCURACY_DEGRADED_THRESHOLD = 50.0  # meters

# In-memory fallback if Redis is unavailable in local dev/test environment
_memory_responder_live: Dict[str, Dict[str, Any]] = {}
_last_published_timestamp: Dict[str, float] = {}
RATE_LIMIT_BROADCAST_INTERVAL = 2.0  # seconds between websocket broadcasts per responder


class ResponderLocationService:
    """
    Manages responder GPS tracking sessions, live Redis caching, and MongoDB persistence.
    """

    @staticmethod
    def _redis_key(responder_id: str) -> str:
        return f"toursafe:responder:location:{responder_id}"

    async def start_tracking_session(self, responder_id: str, device_id: Optional[str] = None) -> str:
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()
        session_id = f"trk_resp_{uuid.uuid4().hex[:12]}"

        session_doc = {
            "tracking_session_id": session_id,
            "responder_id": responder_id,
            "device_id": device_id,
            "started_at": now_iso,
            "ended_at": None,
            "status": "ACTIVE",
            "sample_count": 0,
            "last_location": None,
            "last_location_timestamp": None,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        await db.responder_tracking_sessions.insert_one(session_doc)

        # Update responder tracking state
        await db.responders.update_one(
            {"responder_id": responder_id},
            {
                "$set": {
                    "tracking_session_id": session_id,
                    "tracking_active": True,
                    "updated_at": now_iso,
                }
            },
        )
        return session_id

    async def stop_tracking_session(self, responder_id: str, session_id: Optional[str] = None) -> bool:
        db = get_database()
        now_iso = datetime.now(timezone.utc).isoformat()

        query: Dict[str, Any] = {"responder_id": responder_id, "status": "ACTIVE"}
        if session_id:
            query["tracking_session_id"] = session_id

        res = await db.responder_tracking_sessions.update_many(
            query,
            {"$set": {"status": "COMPLETED", "ended_at": now_iso, "updated_at": now_iso}}
        )

        await db.responders.update_one(
            {"responder_id": responder_id},
            {"$set": {"tracking_active": False, "updated_at": now_iso}}
        )
        return res.modified_count > 0

    async def ingest_responder_location(
        self,
        responder_id: str,
        update: ResponderLocationUpdateRequest,
    ) -> Dict[str, Any]:
        """
        Ingests real GPS coordinates from the responder device.
        1. Caches latest coordinates in Redis (120s TTL).
        2. Appends durable point to MongoDB responder_location_history.
        3. Updates responder record.
        4. Broadcasts rate-controlled realtime event for authority command map.
        """
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()
        sample_ts = update.timestamp or now_iso

        # Assess GPS quality
        accuracy = update.accuracy or 10.0
        is_low_accuracy = accuracy > ACCURACY_DEGRADED_THRESHOLD

        location_payload = {
            "responder_id": responder_id,
            "latitude": update.latitude,
            "longitude": update.longitude,
            "altitude": update.altitude,
            "accuracy": accuracy,
            "heading": update.heading,
            "speed": update.speed,
            "timestamp": sample_ts,
            "tracking_session_id": update.tracking_session_id,
            "is_low_accuracy": is_low_accuracy,
            "quality": "LOW_ACCURACY" if is_low_accuracy else "HIGH_ACCURACY",
        }

        # 1. Update Redis live cache
        redis_client = await get_redis_client()
        r_key = self._redis_key(responder_id)
        if redis_client:
            try:
                await redis_client.set(r_key, json.dumps(location_payload), ex=REDIS_RESPONDER_LOCATION_TTL)
            except Exception as e:
                logger.warning(f"Redis cache write failed for responder {responder_id}: {e}")
                _memory_responder_live[responder_id] = location_payload
        else:
            _memory_responder_live[responder_id] = location_payload

        # 2. Persist in MongoDB
        db = get_database()
        loc_record_id = f"rloc_{uuid.uuid4().hex[:12]}"
        history_doc = {
            "record_id": loc_record_id,
            "responder_id": responder_id,
            "tracking_session_id": update.tracking_session_id,
            "latitude": update.latitude,
            "longitude": update.longitude,
            "altitude": update.altitude,
            "accuracy": accuracy,
            "heading": update.heading,
            "speed": update.speed,
            "location": {
                "type": "Point",
                "coordinates": [update.longitude, update.latitude],
            },
            "timestamp": sample_ts,
            "created_at": now_iso,
        }
        await db.responder_location_history.insert_one(history_doc)

        # 3. Update responder doc current_location & last timestamp
        await db.responders.update_one(
            {"responder_id": responder_id},
            {
                "$set": {
                    "current_location": {
                        "latitude": update.latitude,
                        "longitude": update.longitude,
                        "accuracy": accuracy,
                        "heading": update.heading,
                        "speed": update.speed,
                        "timestamp": sample_ts,
                    },
                    "last_location_timestamp": sample_ts,
                    "updated_at": now_iso,
                }
            },
        )

        # 4. Controlled Realtime publishing
        current_time = now_utc.timestamp()
        last_pub = _last_published_timestamp.get(responder_id, 0.0)
        if current_time - last_pub >= RATE_LIMIT_BROADCAST_INTERVAL:
            _last_published_timestamp[responder_id] = current_time
            await realtime_bus.publish_event(
                event_type=RealtimeEventType.RESPONDER_LOCATION_UPDATED.value,
                payload=location_payload,
                target_role="authority",
            )

        return location_payload

    async def get_live_location(self, responder_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches latest cached location from Redis or fallback.
        """
        redis_client = await get_redis_client()
        r_key = self._redis_key(responder_id)

        if redis_client:
            try:
                data = await redis_client.get(r_key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Redis get failed for responder {responder_id}: {e}")

        # Fallback to memory or MongoDB
        if responder_id in _memory_responder_live:
            return _memory_responder_live[responder_id]

        db = get_database()
        doc = await db.responders.find_one({"responder_id": responder_id})
        if doc and doc.get("current_location"):
            loc = doc["current_location"]
            loc["responder_id"] = responder_id
            return loc
        return None

    def calculate_location_freshness(self, timestamp_str: Optional[str]) -> Tuple[str, Optional[float]]:
        if not timestamp_str:
            return "UNKNOWN", None
        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age = max(0.0, (now - ts).total_seconds())

            if age <= LIVE_THRESHOLD_SECONDS:
                return "LIVE", round(age, 1)
            elif age <= RECENT_THRESHOLD_SECONDS:
                return "RECENT", round(age, 1)
            elif age <= STALE_THRESHOLD_SECONDS:
                return "STALE", round(age, 1)
            else:
                return "OFFLINE", round(age, 1)
        except Exception:
            return "UNKNOWN", None


responder_location_service = ResponderLocationService()
