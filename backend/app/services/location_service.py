import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..core.database import get_database
from ..core.redis import get_redis_client
from ..models.location import GeoJSONPoint, LocationHistoryRecord, TrackingSessionRecord
from ..schemas.location import (
    LiveLocationPayload,
    LiveLocationResponse,
    LocationSampleCreate,
    LocationSampleResponse,
    LocationStaleness,
    TrackingSessionResponse,
    TrackingSessionStatus,
)
from ..schemas.realtime import RealtimeEventEnvelope, RealtimeEventType
from ..services.realtime_bus import realtime_bus
from ..services.geofencing import geofence_engine

logger = logging.getLogger("toursafe.location")

# Configuration constants
REDIS_LIVE_TTL_SECONDS = 120  # 2 minutes TTL for live Redis cache
LIVE_THRESHOLD_SECONDS = 15.0
RECENT_THRESHOLD_SECONDS = 60.0
STALE_THRESHOLD_SECONDS = 300.0

# In-memory degraded cache when Redis is unavailable
_memory_live_store: Dict[str, Tuple[Dict[str, Any], float]] = {}


def calculate_staleness(timestamp_str: Optional[str]) -> Tuple[LocationStaleness, Optional[float]]:
    """
    Computes location staleness state and age in seconds based on GPS timestamp.
    - LIVE: <= 15s
    - RECENT: <= 60s
    - STALE: <= 300s
    - UNKNOWN: > 300s or missing
    """
    if not timestamp_str:
        return LocationStaleness.UNKNOWN, None

    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_seconds = max(0.0, (now - ts).total_seconds())

        if age_seconds <= LIVE_THRESHOLD_SECONDS:
            return LocationStaleness.LIVE, round(age_seconds, 2)
        elif age_seconds <= RECENT_THRESHOLD_SECONDS:
            return LocationStaleness.RECENT, round(age_seconds, 2)
        elif age_seconds <= STALE_THRESHOLD_SECONDS:
            return LocationStaleness.STALE, round(age_seconds, 2)
        else:
            return LocationStaleness.UNKNOWN, round(age_seconds, 2)
    except Exception:
        return LocationStaleness.UNKNOWN, None


class LocationService:
    @staticmethod
    def _redis_key(tourist_id: str) -> str:
        return f"live_location:tourist:{tourist_id}"

    async def ingest_location(
        self,
        user_id: str,
        tourist_id: str,
        sample: LocationSampleCreate,
    ) -> LocationSampleResponse:
        """
        Ingest, validate, store live in Redis, persist in MongoDB, and broadcast realtime location.
        """
        db = get_database()
        now_utc = datetime.now(timezone.utc).isoformat()

        # 1. Build canonical persistent MongoDB record
        record_id = f"loc_{sample.session_id[-6:]}_{sample.sequence_number}_{int(datetime.now(timezone.utc).timestamp())}"
        mongo_doc = LocationHistoryRecord(
            id=record_id,
            location_id=record_id,
            tourist_id=tourist_id,
            user_id=user_id,
            session_id=sample.session_id,
            device_id=sample.device_id,
            timestamp=sample.timestamp,
            latitude=sample.latitude,
            longitude=sample.longitude,
            location=GeoJSONPoint(
                type="Point",
                coordinates=[sample.longitude, sample.latitude],  # GeoJSON: [lon, lat]
            ),
            altitude=sample.altitude,
            accuracy=sample.accuracy,
            speed=sample.speed,
            heading=sample.heading,
            provider=sample.provider or "gps",
            is_background=sample.is_background,
            sequence_number=sample.sequence_number,
            network_status=sample.network_status or "online",
            created_at=now_utc,
        )

        # 2. Persist to MongoDB location_history collection
        try:
            await db.location_history.insert_one(mongo_doc.model_dump())
        except Exception as e:
            logger.error("Failed to insert location_history to MongoDB: %s", e)

        # 3. Update tourist profile current location & last seen
        try:
            await db.tourist_profiles.update_one(
                {"id": tourist_id},
                {
                    "$set": {
                        "current_location": {
                            "latitude": sample.latitude,
                            "longitude": sample.longitude,
                        },
                        "last_seen_at": sample.timestamp,
                        "updated_at": now_utc,
                    }
                },
            )
        except Exception as e:
            logger.debug("Tourist profile update note: %s", e)

        # 4. Update or upsert tracking session
        try:
            await db.tracking_sessions.update_one(
                {"session_id": sample.session_id},
                {
                    "$set": {
                        "last_sequence_number": sample.sequence_number,
                        "last_location_timestamp": sample.timestamp,
                        "status": "active",
                        "updated_at": now_utc,
                    },
                    "$inc": {"sample_count": 1},
                    "$setOnInsert": {
                        "session_id": sample.session_id,
                        "tourist_id": tourist_id,
                        "user_id": user_id,
                        "started_at": sample.timestamp,
                        "created_at": now_utc,
                    },
                },
                upsert=True,
            )
        except Exception as e:
            logger.debug("Tracking session update note: %s", e)

        # 5. Store in Redis Live Location with TTL
        live_payload = {
            "tourist_id": tourist_id,
            "session_id": sample.session_id,
            "latitude": sample.latitude,
            "longitude": sample.longitude,
            "altitude": sample.altitude,
            "accuracy": sample.accuracy,
            "speed": sample.speed,
            "heading": sample.heading,
            "is_background": sample.is_background,
            "sequence_number": sample.sequence_number,
            "timestamp": sample.timestamp,
            "tracking_status": "active",
        }

        redis = await get_redis_client()
        redis_key = self._redis_key(tourist_id)
        if redis is not None:
            try:
                await redis.set(
                    redis_key,
                    json.dumps(live_payload),
                    ex=REDIS_LIVE_TTL_SECONDS,
                )
            except Exception as re:
                logger.warning("Redis live location set error: %s", re)
                # Fallback to in-memory
                import time
                _memory_live_store[tourist_id] = (live_payload, time.time() + REDIS_LIVE_TTL_SECONDS)
        else:
            import time
            _memory_live_store[tourist_id] = (live_payload, time.time() + REDIS_LIVE_TTL_SECONDS)

        # 6. Publish realtime location.updated event
        event_payload = {
            "tourist_id": tourist_id,
            "session_id": sample.session_id,
            "location": {
                "latitude": sample.latitude,
                "longitude": sample.longitude,
                "altitude": sample.altitude,
                "accuracy": sample.accuracy,
                "speed": sample.speed,
                "heading": sample.heading,
                "is_background": sample.is_background,
            },
            "timestamp": sample.timestamp,
            "sequence_number": sample.sequence_number,
            "tracking_status": "active",
        }

        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.LOCATION_UPDATED.value,
            source="gps_tracking_pipeline",
            payload=event_payload,
        )

        # Broadcast to tourist private channel and authority operations channel
        try:
            await realtime_bus.publish_to_channel(f"tourist:{tourist_id}", envelope)
            await realtime_bus.publish_to_channel("authority:operations", envelope)
        except Exception as pe:
            logger.warning("Realtime broadcast note for location.updated: %s", pe)

        # 7. Process real-time geo-fencing (Prompt 10)
        try:
            await geofence_engine.process_location_sample(
                tourist_id=tourist_id,
                user_id=user_id,
                location_sample=sample,
            )
        except Exception as ge_err:
            logger.error("Geofencing engine processing error for tourist %s: %s", tourist_id, ge_err)

        return LocationSampleResponse(
            location_id=mongo_doc.location_id,
            tourist_id=tourist_id,
            session_id=sample.session_id,
            timestamp=sample.timestamp,
            latitude=sample.latitude,
            longitude=sample.longitude,
            altitude=sample.altitude,
            accuracy=sample.accuracy,
            speed=sample.speed,
            heading=sample.heading,
            provider=sample.provider or "gps",
            is_background=sample.is_background,
            sequence_number=sample.sequence_number,
            created_at=mongo_doc.created_at,
        )

    async def get_live_location(self, tourist_id: str) -> LiveLocationResponse:
        """
        Retrieves the latest live location for a tourist.
        Checks Redis live cache first; falls back to MongoDB history if expired.
        Calculates staleness (LIVE, RECENT, STALE, UNKNOWN).
        """
        # 1. Try Redis
        redis = await get_redis_client()
        raw_data = None
        if redis is not None:
            try:
                raw_data = await redis.get(self._redis_key(tourist_id))
            except Exception as e:
                logger.warning("Redis read error: %s", e)

        # In-memory fallback if Redis missed/unavailable
        if not raw_data and tourist_id in _memory_live_store:
            import time
            payload, expire_at = _memory_live_store[tourist_id]
            if time.time() <= expire_at:
                raw_data = json.dumps(payload)
            else:
                _memory_live_store.pop(tourist_id, None)

        if raw_data:
            try:
                data = json.loads(raw_data)
                staleness, age_seconds = calculate_staleness(data.get("timestamp"))
                return LiveLocationResponse(
                    tourist_id=tourist_id,
                    location=LiveLocationPayload(
                        latitude=data["latitude"],
                        longitude=data["longitude"],
                        altitude=data.get("altitude"),
                        accuracy=data.get("accuracy"),
                        speed=data.get("speed"),
                        heading=data.get("heading"),
                        is_background=data.get("is_background", False),
                    ),
                    timestamp=data.get("timestamp"),
                    session_id=data.get("session_id"),
                    sequence_number=data.get("sequence_number"),
                    tracking_status=data.get("tracking_status", "active"),
                    staleness=staleness,
                    age_seconds=age_seconds,
                )
            except Exception as e:
                logger.error("Error parsing live location from Redis: %s", e)

        # 2. Redis missed / TTL expired: Fallback to MongoDB latest record
        db = get_database()
        latest_doc = await db.location_history.find_one(
            {"tourist_id": tourist_id},
            sort=[("timestamp", -1)],
        )

        if latest_doc:
            staleness, age_seconds = calculate_staleness(latest_doc.get("timestamp"))
            # When Redis TTL is expired, even recent timestamps are considered STALE
            if staleness == LocationStaleness.LIVE:
                staleness = LocationStaleness.RECENT

            return LiveLocationResponse(
                tourist_id=tourist_id,
                location=LiveLocationPayload(
                    latitude=latest_doc["latitude"],
                    longitude=latest_doc["longitude"],
                    altitude=latest_doc.get("altitude"),
                    accuracy=latest_doc.get("accuracy"),
                    speed=latest_doc.get("speed"),
                    heading=latest_doc.get("heading"),
                    is_background=latest_doc.get("is_background", False),
                ),
                timestamp=latest_doc.get("timestamp"),
                session_id=latest_doc.get("session_id"),
                sequence_number=latest_doc.get("sequence_number"),
                tracking_status="stale",
                staleness=staleness,
                age_seconds=age_seconds,
            )

        return LiveLocationResponse(
            tourist_id=tourist_id,
            location=None,
            timestamp=None,
            session_id=None,
            sequence_number=None,
            tracking_status="stopped",
            staleness=LocationStaleness.UNKNOWN,
            age_seconds=None,
        )

    async def get_all_live_locations(self) -> List[LiveLocationResponse]:
        """
        Returns all current live locations across all active tourists.
        Used by the Authority Live Map.
        """
        results: List[LiveLocationResponse] = []
        redis = await get_redis_client()

        if redis is not None:
            try:
                keys = await redis.keys("live_location:tourist:*")
                for k in keys:
                    raw = await redis.get(k)
                    if raw:
                        try:
                            data = json.loads(raw)
                            tourist_id = data.get("tourist_id")
                            if tourist_id:
                                staleness, age_seconds = calculate_staleness(data.get("timestamp"))
                                results.append(
                                    LiveLocationResponse(
                                        tourist_id=tourist_id,
                                        location=LiveLocationPayload(
                                            latitude=data["latitude"],
                                            longitude=data["longitude"],
                                            altitude=data.get("altitude"),
                                            accuracy=data.get("accuracy"),
                                            speed=data.get("speed"),
                                            heading=data.get("heading"),
                                            is_background=data.get("is_background", False),
                                        ),
                                        timestamp=data.get("timestamp"),
                                        session_id=data.get("session_id"),
                                        sequence_number=data.get("sequence_number"),
                                        tracking_status=data.get("tracking_status", "active"),
                                        staleness=staleness,
                                        age_seconds=age_seconds,
                                    )
                                )
                        except Exception:
                            pass
                return results
            except Exception as e:
                logger.warning("Redis keys scan error: %s", e)

        # Fallback to in-memory store
        import time
        now = time.time()
        for t_id, (data, expire_at) in list(_memory_live_store.items()):
            if now <= expire_at:
                staleness, age_seconds = calculate_staleness(data.get("timestamp"))
                results.append(
                    LiveLocationResponse(
                        tourist_id=t_id,
                        location=LiveLocationPayload(
                            latitude=data["latitude"],
                            longitude=data["longitude"],
                            altitude=data.get("altitude"),
                            accuracy=data.get("accuracy"),
                            speed=data.get("speed"),
                            heading=data.get("heading"),
                            is_background=data.get("is_background", False),
                        ),
                        timestamp=data.get("timestamp"),
                        session_id=data.get("session_id"),
                        sequence_number=data.get("sequence_number"),
                        tracking_status=data.get("tracking_status", "active"),
                        staleness=staleness,
                        age_seconds=age_seconds,
                    )
                )

        return results

    async def get_location_history(
        self,
        tourist_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> Tuple[List[LocationSampleResponse], int]:
        """
        Query MongoDB location history for a tourist with filtering and pagination.
        """
        db = get_database()
        query: Dict[str, Any] = {"tourist_id": tourist_id}

        if start_time or end_time:
            time_filter: Dict[str, Any] = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            query["timestamp"] = time_filter

        limit = max(1, min(limit, 500))
        skip = max(0, skip)

        total = await db.location_history.count_documents(query)
        cursor = (
            db.location_history.find(query)
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )

        items: List[LocationSampleResponse] = []
        async for doc in cursor:
            items.append(
                LocationSampleResponse(
                    location_id=doc.get("location_id") or doc.get("id"),
                    tourist_id=doc.get("tourist_id"),
                    session_id=doc.get("session_id"),
                    timestamp=doc.get("timestamp"),
                    latitude=doc.get("latitude"),
                    longitude=doc.get("longitude"),
                    altitude=doc.get("altitude"),
                    accuracy=doc.get("accuracy"),
                    speed=doc.get("speed"),
                    heading=doc.get("heading"),
                    provider=doc.get("provider", "gps"),
                    is_background=doc.get("is_background", False),
                    sequence_number=doc.get("sequence_number", 1),
                    created_at=doc.get("created_at", doc.get("timestamp")),
                )
            )

        return items, total

    async def start_session(
        self,
        user_id: str,
        tourist_id: str,
        device_id: Optional[str] = None,
        source: Optional[str] = "mobile_app",
    ) -> TrackingSessionResponse:
        """
        Start or reactivate a tracking session.
        """
        db = get_database()
        import uuid
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat()

        session_record = TrackingSessionRecord(
            session_id=session_id,
            tourist_id=tourist_id,
            user_id=user_id,
            device_id=device_id,
            started_at=now_utc,
            status=TrackingSessionStatus.ACTIVE.value,
            source=source or "mobile_app",
            sample_count=0,
            created_at=now_utc,
            updated_at=now_utc,
        )

        await db.tracking_sessions.insert_one(session_record.model_dump())

        return TrackingSessionResponse(
            session_id=session_id,
            tourist_id=tourist_id,
            user_id=user_id,
            status=TrackingSessionStatus.ACTIVE.value,
            started_at=now_utc,
            last_sequence_number=0,
            sample_count=0,
        )

    async def stop_session(
        self,
        user_id: str,
        tourist_id: str,
        session_id: str,
    ) -> TrackingSessionResponse:
        """
        Stop an active tracking session.
        """
        db = get_database()
        now_utc = datetime.now(timezone.utc).isoformat()

        doc = await db.tracking_sessions.find_one_and_update(
            {"session_id": session_id, "tourist_id": tourist_id},
            {
                "$set": {
                    "status": TrackingSessionStatus.STOPPED.value,
                    "ended_at": now_utc,
                    "updated_at": now_utc,
                }
            },
            return_document=True,
        )

        # Clear Redis live record or mark status stopped
        redis = await get_redis_client()
        if redis is not None:
            try:
                await redis.delete(self._redis_key(tourist_id))
            except Exception:
                pass
        _memory_live_store.pop(tourist_id, None)

        if doc:
            return TrackingSessionResponse(
                session_id=session_id,
                tourist_id=tourist_id,
                user_id=user_id,
                status=TrackingSessionStatus.STOPPED.value,
                started_at=doc.get("started_at", now_utc),
                ended_at=now_utc,
                last_sequence_number=doc.get("last_sequence_number", 0),
                sample_count=doc.get("sample_count", 0),
            )

        return TrackingSessionResponse(
            session_id=session_id,
            tourist_id=tourist_id,
            user_id=user_id,
            status=TrackingSessionStatus.STOPPED.value,
            started_at=now_utc,
            ended_at=now_utc,
            last_sequence_number=0,
            sample_count=0,
        )


location_service = LocationService()
