"""
TourSafe Redis Active Safety State & Signals Cache

Provides sub-millisecond ephemeral state caching:
- Active Safety State (TTL 300s)
- Active Subsystem Signals (TTL 120s)
- In-memory degraded fallback when Redis is offline
- Seamless server restart reconstruction
"""

from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from ...core.redis import get_redis_client
from ...schemas.safety import ActiveSafetyState, SafetyDecision, SafetySignal, SafetyState, SignalQuality, SignalType
from .config import safety_config
from .repository import safety_repository

logger = logging.getLogger("toursafe.safety.redis")

# In-memory fallbacks when Redis is offline
_memory_active_states: Dict[str, Tuple[Dict[str, Any], float]] = {}
_memory_active_signals: Dict[str, Dict[str, Tuple[Dict[str, Any], float]]] = {}


class SafetyRedisState:
    """
    Manages active safety state and signals in Redis with in-memory fallback.
    """

    @staticmethod
    def _state_key(tourist_id: str) -> str:
        return f"toursafe:safety:state:{tourist_id}"

    @staticmethod
    def _signals_key(tourist_id: str) -> str:
        return f"toursafe:safety:signals:{tourist_id}"

    async def get_active_state(self, tourist_id: str) -> Optional[ActiveSafetyState]:
        """Retrieves active safety state for tourist from Redis or in-memory cache."""
        redis = await get_redis_client()
        raw = None
        if redis is not None:
            try:
                raw = await redis.get(self._state_key(tourist_id))
            except Exception as e:
                logger.warning("Redis safety state read error: %s", e)

        # In-memory fallback
        if not raw and tourist_id in _memory_active_states:
            data_dict, expire_at = _memory_active_states[tourist_id]
            if time.time() <= expire_at:
                return ActiveSafetyState(**data_dict)
            else:
                _memory_active_states.pop(tourist_id, None)

        if raw:
            try:
                data = json.loads(raw)
                return ActiveSafetyState(**data)
            except Exception as e:
                logger.error("Error deserializing active safety state: %s", e)

        # Reconstruct from MongoDB on cold start / cache miss
        return await self._reconstruct_from_db(tourist_id)

    async def set_active_state(self, state: ActiveSafetyState) -> None:
        """Saves active safety state to Redis with TTL and in-memory fallback."""
        serializable = state.model_dump()
        _memory_active_states[state.tourist_id] = (
            serializable,
            time.time() + safety_config.redis_state_ttl_seconds,
        )
        redis = await get_redis_client()
        if redis is not None:
            try:
                await redis.set(
                    self._state_key(state.tourist_id),
                    json.dumps(serializable),
                    ex=safety_config.redis_state_ttl_seconds,
                )
            except Exception as e:
                logger.warning("Redis safety state write error: %s", e)

    async def get_active_signals(self, tourist_id: str) -> List[SafetySignal]:
        """Retrieves all active signals for tourist."""
        redis = await get_redis_client()
        signals: List[SafetySignal] = []

        if redis is not None:
            try:
                raw_dict = await redis.hgetall(self._signals_key(tourist_id))
                if raw_dict:
                    for sig_key, sig_json in raw_dict.items():
                        try:
                            data = json.loads(sig_json)
                            signals.append(SafetySignal(**data))
                        except Exception:
                            pass
                    if signals:
                        return signals
            except Exception as e:
                logger.warning("Redis safety signals read error: %s", e)

        # In-memory fallback
        if tourist_id in _memory_active_signals:
            now = time.time()
            sig_dict = _memory_active_signals[tourist_id]
            valid_signals = []
            for k, (s_data, expire_at) in list(sig_dict.items()):
                if now <= expire_at:
                    valid_signals.append(SafetySignal(**s_data))
                else:
                    sig_dict.pop(k, None)
            return valid_signals

        return []

    async def update_active_signal(self, signal: SafetySignal) -> None:
        """Stores or updates a single active safety signal in the tourist's signal set."""
        key_field = f"{signal.signal_type.value}:{signal.source}"
        serializable = signal.model_dump()

        if signal.tourist_id not in _memory_active_signals:
            _memory_active_signals[signal.tourist_id] = {}
        _memory_active_signals[signal.tourist_id][key_field] = (
            serializable,
            time.time() + safety_config.signal_expiry_seconds,
        )

        redis = await get_redis_client()
        if redis is not None:
            try:
                pipe = redis.pipeline()
                pipe.hset(self._signals_key(signal.tourist_id), key_field, json.dumps(serializable))
                pipe.expire(self._signals_key(signal.tourist_id), int(safety_config.signal_expiry_seconds))
                await pipe.execute()
            except Exception as e:
                logger.warning("Redis safety signal write error: %s", e)

    async def _reconstruct_from_db(self, tourist_id: str) -> Optional[ActiveSafetyState]:
        """Rebuilds active safety state from MongoDB history after server restart."""
        try:
            decisions, total = await safety_repository.get_decision_history(tourist_id, limit=1)
            if decisions:
                last_dec = decisions[0]
                active_inc = await safety_repository.get_active_incident(tourist_id)
                reconstructed = ActiveSafetyState(
                    tourist_id=tourist_id,
                    current_state=last_dec.state,
                    previous_state=last_dec.previous_state,
                    decision_id=last_dec.decision_id,
                    started_at=last_dec.timestamp,
                    last_update=last_dec.timestamp,
                    rule_version=last_dec.rule_version,
                    confidence_class=last_dec.confidence_class,
                    active_reasons=last_dec.reasons,
                    active_signals_summary=last_dec.signals,
                    active_incident_id=active_inc.incident_id if active_inc else None,
                )
                await self.set_active_state(reconstructed)
                return reconstructed
        except Exception as e:
            logger.error("Failed to reconstruct safety state for %s: %s", tourist_id, e)

        return None


safety_redis_state = SafetyRedisState()
