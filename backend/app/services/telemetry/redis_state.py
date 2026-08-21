import json
import logging
import time
from typing import Any, Dict, List, Optional
from ...core.config import settings
from ...core import redis as redis_core
from ...schemas.telemetry import (
    QualityMetrics,
    QualityStateEnum,
    SessionStatusEnum,
    TelemetrySample,
)

logger = logging.getLogger("toursafe.telemetry.redis")

# Fallback in-memory store for degraded offline operation
_memory_telemetry_live: Dict[str, Dict[str, Any]] = {}
_memory_telemetry_expiry: Dict[str, float] = {}


class TelemetryRedisStateManager:
    """
    Manages high-throughput live telemetry state in Redis with automatic TTL expiration.
    Namespaces:
    - toursafe:telemetry:live:{tourist_id} -> Latest tourist telemetry snapshot
    - toursafe:telemetry:session:{session_id} -> Active session telemetry state
    - toursafe:telemetry:quality:{session_id} -> Current quality metrics
    """

    @staticmethod
    def key_live(tourist_id: str) -> str:
        return f"toursafe:telemetry:live:{tourist_id}"

    @staticmethod
    def key_session(session_id: str) -> str:
        return f"toursafe:telemetry:session:{session_id}"

    @staticmethod
    def key_quality(session_id: str) -> str:
        return f"toursafe:telemetry:quality:{session_id}"

    async def update_live_state(
        self,
        sample: TelemetrySample,
        quality: QualityMetrics,
        session_status: SessionStatusEnum = SessionStatusEnum.ACTIVE,
    ) -> bool:
        """
        Updates live telemetry state in Redis cache with configured TTL.
        """
        ttl = settings.telemetry_redis_ttl_seconds
        payload: Dict[str, Any] = {
            "tourist_id": sample.tourist_id,
            "session_id": sample.session_id,
            "device_id": sample.device_id,
            "sequence_number": sample.sequence_number,
            "packet_id": sample.packet_id,
            "timestamp": sample.timestamp,
            "received_at": sample.received_at,
            "tracking_status": session_status.value,
            "is_background": sample.is_background,
            "network_status": sample.network_status,
            "overall_quality": quality.overall_quality.value,
            "gps_quality": quality.gps_quality.value,
            "imu_quality": quality.imu_quality.value,
            "sync_quality": quality.synchronization_quality.value,
            "observed_frequency_hz": quality.observed_frequency_hz,
        }

        if sample.gps:
            payload["last_gps"] = sample.gps.model_dump()
        if sample.accelerometer and sample.gyroscope:
            payload["last_imu"] = {
                "accelerometer": sample.accelerometer.model_dump(),
                "gyroscope": sample.gyroscope.model_dump(),
                "derived": sample.derived.model_dump() if sample.derived else None,
            }

        redis = await redis_core.get_redis_client()
        if redis is not None:
            try:
                pipe = redis.pipeline()
                pipe.set(self.key_live(sample.tourist_id), json.dumps(payload), ex=ttl)
                pipe.set(self.key_session(sample.session_id), json.dumps(payload), ex=ttl)
                pipe.set(self.key_quality(sample.session_id), json.dumps(quality.model_dump()), ex=ttl)
                await pipe.execute()
                return True
            except Exception as e:
                logger.warning("Redis live state write error: %s", e)

        # In-memory degraded fallback
        now = time.time()
        _memory_telemetry_live[sample.tourist_id] = payload
        _memory_telemetry_expiry[sample.tourist_id] = now + ttl
        return True

    async def get_live_state(self, tourist_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the live state for a tourist."""
        redis = await redis_core.get_redis_client()
        if redis is not None:
            try:
                raw = await redis.get(self.key_live(tourist_id))
                if raw:
                    return json.loads(raw)
            except Exception as e:
                logger.warning("Redis live state read error: %s", e)

        # Fallback
        if tourist_id in _memory_telemetry_live:
            if time.time() <= _memory_telemetry_expiry.get(tourist_id, 0):
                return _memory_telemetry_live[tourist_id]
            else:
                _memory_telemetry_live.pop(tourist_id, None)
                _memory_telemetry_expiry.pop(tourist_id, None)

        return None

    async def clear_live_state(self, tourist_id: str, session_id: Optional[str] = None):
        """Clears live telemetry keys upon session stop or disconnect."""
        redis = await redis_core.get_redis_client()
        if redis is not None:
            try:
                keys = [self.key_live(tourist_id)]
                if session_id:
                    keys.extend([self.key_session(session_id), self.key_quality(session_id)])
                await redis.delete(*keys)
            except Exception as e:
                logger.warning("Redis clear live state error: %s", e)

        _memory_telemetry_live.pop(tourist_id, None)
        _memory_telemetry_expiry.pop(tourist_id, None)


telemetry_redis_state = TelemetryRedisStateManager()
