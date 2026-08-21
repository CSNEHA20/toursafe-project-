"""
TourSafe ML Redis Live State Manager.
Maintains high-performance cached active anomaly state in Redis:
Key: toursafe:anomaly:active:{tourist_id}
"""

import json
import logging
from typing import Any, Dict, Optional
from ...core import redis as redis_core
from ...schemas.ml import AnomalyEpisode

logger = logging.getLogger("toursafe.ml.redis")


class AnomalyRedisState:
    """
    Manages active ephemeral anomaly state in Redis with automatic TTL expiration.
    """

    def __init__(self, default_ttl_seconds: int = 180):
        self.default_ttl_seconds = default_ttl_seconds

    def _get_key(self, tourist_id: str) -> str:
        return f"toursafe:anomaly:active:{tourist_id}"

    async def update_active_anomaly(self, episode: AnomalyEpisode) -> bool:
        """
        Sets or refreshes active anomaly state in Redis with TTL.
        """
        try:
            client = await redis_core.get_redis_client()
            if not client:
                return False

            key = self._get_key(episode.tourist_id)
            payload = {
                "anomaly_id": episode.anomaly_id,
                "tourist_id": episode.tourist_id,
                "session_id": episode.session_id,
                "model_version": episode.model_version,
                "current_score": episode.current_score,
                "peak_score": episode.peak_score,
                "threshold": episode.threshold,
                "window_count": episode.window_count,
                "duration_seconds": episode.duration_seconds,
                "started_at": episode.started_at,
                "last_update": episode.updated_at,
                "status": episode.status,
                "quality": episode.quality,
                "last_known_gps": episode.last_known_gps,
            }

            await client.set(key, json.dumps(payload), ex=self.default_ttl_seconds)
            return True
        except Exception as e:
            logger.debug(f"Redis active anomaly update note: {e}")
            return False

    async def get_active_anomaly(self, tourist_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves current active anomaly state for a tourist from Redis.
        """
        try:
            client = await redis_core.get_redis_client()
            if not client:
                return None

            key = self._get_key(tourist_id)
            raw = await client.get(key)
            if raw:
                return json.loads(raw)
            return None
        except Exception as e:
            logger.debug(f"Redis active anomaly lookup note: {e}")
            return None

    async def clear_active_anomaly(self, tourist_id: str) -> bool:
        """
        Deletes active anomaly state key from Redis when resolved.
        """
        try:
            client = await redis_core.get_redis_client()
            if not client:
                return False

            key = self._get_key(tourist_id)
            await client.delete(key)
            return True
        except Exception as e:
            logger.debug(f"Redis active anomaly delete note: {e}")
            return False


anomaly_redis_state = AnomalyRedisState(default_ttl_seconds=180)
