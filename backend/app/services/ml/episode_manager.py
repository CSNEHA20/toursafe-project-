"""
TourSafe Anomaly Episode Manager & Deduplication Engine.
Maintains single active anomaly episodes for sustained sensor anomalies,
updating peak scores and duration instead of creating redundant alert records.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional, Tuple
import uuid

from ...schemas.ml import (
    AnomalyClearedEventPayload,
    AnomalyDetectedEventPayload,
    AnomalyEpisode,
    AnomalyState,
)
from ...schemas.telemetry import TelemetryWindow
from .loader import model_loader

logger = logging.getLogger("toursafe.ml.episode_manager")


class AnomalyEpisodeManager:
    """
    Manages active episode lifecycles, event deduplication, and persistence payloads.
    """

    def __init__(self):
        # Maps tourist_id -> active AnomalyEpisode
        self._active_episodes: Dict[str, AnomalyEpisode] = {}

    def get_active_episode(self, tourist_id: str) -> Optional[AnomalyEpisode]:
        return self._active_episodes.get(tourist_id)

    def get_all_active_episodes(self) -> Dict[str, AnomalyEpisode]:
        return dict(self._active_episodes)

    def handle_window_transition(
        self,
        window: TelemetryWindow,
        score: float,
        prev_state: AnomalyState,
        new_state: AnomalyState,
        became_anomalous: bool,
        became_cleared: bool,
    ) -> Tuple[Optional[AnomalyDetectedEventPayload], Optional[AnomalyClearedEventPayload], Optional[AnomalyEpisode]]:
        """
        Coordinates episode updates and determines if realtime events should be emitted.
        """
        tourist_id = window.tourist_id
        session_id = window.session_id
        now_iso = datetime.now(timezone.utc).isoformat()
        now_dt = datetime.now(timezone.utc)

        detected_event: Optional[AnomalyDetectedEventPayload] = None
        cleared_event: Optional[AnomalyClearedEventPayload] = None
        saved_episode: Optional[AnomalyEpisode] = None

        gps_info = None
        if window.gps_context:
            gps_info = {
                "latitude": window.gps_context.latitude,
                "longitude": window.gps_context.longitude,
                "accuracy": window.gps_context.accuracy,
                "altitude": window.gps_context.altitude,
                "speed": window.gps_context.speed,
            }

        quality_dict = {
            "overall_quality": window.quality.overall_quality.value if window.quality else "good",
            "gps_quality": window.quality.gps_quality.value if window.quality else "unavailable",
            "imu_quality": window.quality.imu_quality.value if window.quality else "good",
            "observed_frequency_hz": window.observed_frequency_hz,
            "completeness_ratio": window.completeness_ratio,
        }

        # Case 1: Became Anomalous -> Start new episode
        if became_anomalous:
            anomaly_id = f"anom_{uuid.uuid4().hex[:12]}"
            episode = AnomalyEpisode(
                anomaly_id=anomaly_id,
                tourist_id=tourist_id,
                session_id=session_id,
                model_version=model_loader.metadata.model_version if model_loader.metadata else "v1.0.0",
                started_at=now_iso,
                status="active",
                current_score=round(score, 4),
                peak_score=round(score, 4),
                threshold=model_loader.primary_threshold,
                window_count=1,
                duration_seconds=0.0,
                quality=quality_dict,
                last_known_gps=gps_info,
                created_at=now_iso,
                updated_at=now_iso,
            )
            self._active_episodes[tourist_id] = episode
            saved_episode = episode

            detected_event = AnomalyDetectedEventPayload(
                anomaly_id=anomaly_id,
                tourist_id=tourist_id,
                session_id=session_id,
                model_version=episode.model_version,
                timestamp=now_iso,
                window_start=window.window_start,
                window_end=window.window_end,
                anomaly_score=round(score, 4),
                threshold=model_loader.primary_threshold,
                persistence_count=2,
                quality=quality_dict,
                last_known_gps=gps_info,
            )
            logger.info(f"🚨 Anomaly Episode [{anomaly_id}] STARTED for tourist {tourist_id} (Score: {score:.4f} >= {model_loader.primary_threshold:.4f})")

        # Case 2: Continuing in ANOMALOUS or RECOVERING state -> Update existing episode
        elif tourist_id in self._active_episodes and (new_state in [AnomalyState.ANOMALOUS, AnomalyState.RECOVERING]):
            episode = self._active_episodes[tourist_id]
            episode.window_count += 1
            episode.current_score = round(score, 4)
            episode.peak_score = round(max(episode.peak_score, score), 4)
            episode.quality = quality_dict
            if gps_info:
                episode.last_known_gps = gps_info
            episode.updated_at = now_iso

            start_dt = datetime.fromisoformat(episode.started_at.replace("Z", "+00:00"))
            episode.duration_seconds = round((now_dt - start_dt).total_seconds(), 2)
            saved_episode = episode

        # Case 3: Became Cleared -> Resolve active episode
        if became_cleared and tourist_id in self._active_episodes:
            episode = self._active_episodes.pop(tourist_id)
            episode.cleared_at = now_iso
            episode.status = "resolved"
            episode.updated_at = now_iso
            start_dt = datetime.fromisoformat(episode.started_at.replace("Z", "+00:00"))
            episode.duration_seconds = round((now_dt - start_dt).total_seconds(), 2)
            saved_episode = episode

            cleared_event = AnomalyClearedEventPayload(
                anomaly_id=episode.anomaly_id,
                tourist_id=tourist_id,
                session_id=session_id,
                model_version=episode.model_version,
                timestamp=now_iso,
                duration_seconds=episode.duration_seconds,
                peak_score=episode.peak_score,
                recovery_score=round(score, 4),
                threshold=model_loader.primary_threshold,
            )
            logger.info(f"✅ Anomaly Episode [{episode.anomaly_id}] CLEARED for tourist {tourist_id} after {episode.duration_seconds}s (Peak score: {episode.peak_score:.4f})")

        return detected_event, cleared_event, saved_episode

    def clear_tourist(self, tourist_id: str):
        self._active_episodes.pop(tourist_id, None)


anomaly_episode_manager = AnomalyEpisodeManager()
