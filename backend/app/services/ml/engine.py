"""
TourSafe Real-Time ML Inference Engine.
Connects the live telemetry pipeline to the LSTM autoencoder:
- Bounded asynchronous queue with backpressure protection
- Sub-millisecond preprocessing, inference, and reconstruction scoring
- Temporal persistence & hysteresis state machine evaluation
- Anomaly episode deduplication and lifecycle management
- Redis live state synchronization and MongoDB durable persistence
- Realtime event dispatching to authorized authority operational channels.
"""

import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, Optional, Tuple
import uuid

from ...schemas.ml import (
    AnomalyState,
    InferenceLatencyBreakdown,
    InferenceQualityInfo,
    InferenceResult,
    InferenceStatus,
    ModelHealthState,
)
from ...schemas.realtime import RealtimeEventEnvelope, RealtimeEventType
from ...schemas.telemetry import TelemetryWindow
from ..realtime_bus import realtime_bus
from .anomaly_scorer import anomaly_scorer
from .episode_manager import anomaly_episode_manager
from .loader import model_loader
from .metrics import ml_metrics_tracker
from .persistence import anomaly_persistence
from .preprocessor import inference_preprocessor
from .redis_state import anomaly_redis_state
from .state_machine import anomaly_state_machine
from ..safety import safety_orchestrator, SafetySignalFactory
from ...ml.lifecycle.shadow_engine import shadow_engine

logger = logging.getLogger("toursafe.ml.engine")


class RealtimeInferenceEngine:
    """
    Asynchronous ML Inference Engine.
    Processes validated 3-second telemetry windows from a bounded FIFO queue.
    """

    def __init__(self, queue_capacity: int = 1000):
        self.queue_capacity = queue_capacity
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_capacity)
        self._worker_task: Optional[asyncio.Task] = None
        self._is_running: bool = False

    async def start(self):
        """Initializes model loading, database indexes, and starts the background inference worker."""
        if self._is_running:
            return

        logger.info("Initializing TourSafe Real-Time ML Inference Engine...")
        model_loader.load_and_validate()
        await anomaly_persistence.init_indexes()

        self._is_running = True
        self._worker_task = asyncio.create_task(self._inference_worker_loop())
        logger.info("✅ ML Inference Engine background worker started successfully")

    async def stop(self):
        """Gracefully halts the inference worker."""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        logger.info("ML Inference Engine stopped")

    def submit_window(self, window: TelemetryWindow) -> bool:
        """
        Non-blocking window submission from telemetry ingestion pipeline.
        Drops window with metric recording if queue is full to prevent pipeline stall.
        """
        if not self._is_running:
            return False

        t_enqueue = time.time()
        try:
            self._queue.put_nowait((t_enqueue, window))
            return True
        except asyncio.QueueFull:
            ml_metrics_tracker.record_dropped_window()
            logger.warning(
                f"ML Inference queue full ({self._queue.qsize()}/{self.queue_capacity}). Dropping window {window.window_id} for tourist {window.tourist_id}"
            )
            return False

    async def _inference_worker_loop(self):
        """Dedicated background inference consumer worker."""
        while self._is_running:
            try:
                t_enqueue, window = await self._queue.get()
                await self.process_single_window(window, t_enqueue)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in ML inference worker loop: {e}", exc_info=True)
                ml_metrics_tracker.record_failure(str(e))
                await asyncio.sleep(0.01)

    async def process_single_window(
        self,
        window: TelemetryWindow,
        t_enqueue: Optional[float] = None,
    ) -> InferenceResult:
        """
        Executes end-to-end inference pipeline for a single TelemetryWindow:
        Validation -> Preprocessing -> Model Inference -> Anomaly Scoring ->
        State Machine -> Episode Management -> Redis/Mongo Sync -> Authority WebSocket.
        """
        t_start = time.time()
        queue_wait_ms = (t_start - t_enqueue) * 1000.0 if t_enqueue else 0.0

        model_ver = model_loader.metadata.model_version if model_loader.metadata else "v1.0.0"
        thresh = model_loader.primary_threshold
        recov_thresh = model_loader.warning_threshold

        quality_info = InferenceQualityInfo(
            overall_quality=window.quality.overall_quality.value if window.quality else "good",
            gps_quality=window.quality.gps_quality.value if window.quality else "unavailable",
            imu_quality=window.quality.imu_quality.value if window.quality else "good",
            observed_frequency_hz=window.observed_frequency_hz or 50.0,
            completeness_ratio=window.completeness_ratio or 1.0,
        )

        # 1. Gating & Validation Check
        if not window.is_valid:
            ml_metrics_tracker.record_skipped_window()
            return InferenceResult(
                window_id=window.window_id,
                tourist_id=window.tourist_id,
                session_id=window.session_id,
                model_version=model_ver,
                threshold=thresh,
                state=AnomalyState.NORMAL,
                quality=quality_info,
                status=InferenceStatus.SKIPPED,
                reason="; ".join(window.validation_errors) if window.validation_errors else "Window invalid",
            )

        if model_loader.health_state != ModelHealthState.MODEL_READY:
            ml_metrics_tracker.record_skipped_window()
            return InferenceResult(
                window_id=window.window_id,
                tourist_id=window.tourist_id,
                session_id=window.session_id,
                model_version=model_ver,
                threshold=thresh,
                state=AnomalyState.NORMAL,
                quality=quality_info,
                status=InferenceStatus.SKIPPED,
                reason=f"Model not ready (state: {model_loader.health_state})",
            )

        # 2. Preprocessing
        t_pre_start = time.time()
        tensor_in, prep_error = inference_preprocessor.preprocess_window(window)
        t_pre_end = time.time()
        preprocessing_ms = (t_pre_end - t_pre_start) * 1000.0

        if prep_error or tensor_in is None:
            ml_metrics_tracker.record_skipped_window()
            return InferenceResult(
                window_id=window.window_id,
                tourist_id=window.tourist_id,
                session_id=window.session_id,
                model_version=model_ver,
                threshold=thresh,
                state=AnomalyState.NORMAL,
                quality=quality_info,
                status=InferenceStatus.SKIPPED,
                reason=prep_error or "Preprocessing returned null tensor",
            )

        # 3. Model Inference (LSTM Autoencoder reconstruction)
        t_inf_start = time.time()
        try:
            recon_tensor = model_loader.infer_raw(tensor_in)
        except Exception as ie:
            ml_metrics_tracker.record_failure(f"Model inference failed: {ie}")
            return InferenceResult(
                window_id=window.window_id,
                tourist_id=window.tourist_id,
                session_id=window.session_id,
                model_version=model_ver,
                threshold=thresh,
                state=AnomalyState.NORMAL,
                quality=quality_info,
                status=InferenceStatus.FAILED,
                reason=f"Model inference execution exception: {ie}",
            )
        t_inf_end = time.time()
        model_inference_ms = (t_inf_end - t_inf_start) * 1000.0

        # 4. Postprocessing & Anomaly Score Calculation
        t_post_start = time.time()
        raw_score = anomaly_scorer.compute_mse_score(tensor_in, recon_tensor)
        score = round(raw_score, 4)

        # 5. State Machine Evaluation (Temporal Persistence + Hysteresis)
        prev_state, new_state, became_anomalous, became_cleared = (
            anomaly_state_machine.evaluate_window(
                tourist_id=window.tourist_id,
                session_id=window.session_id,
                anomaly_score=score,
                anomaly_threshold=thresh,
                recovery_threshold=recov_thresh,
            )
        )

        # 6. Episode Management & Deduplication
        detected_evt, cleared_evt, episode = anomaly_episode_manager.handle_window_transition(
            window=window,
            score=score,
            prev_state=prev_state,
            new_state=new_state,
            became_anomalous=became_anomalous,
            became_cleared=became_cleared,
        )

        t_post_end = time.time()
        postprocessing_ms = (t_post_end - t_post_start) * 1000.0
        total_inference_ms = (t_post_end - t_start) * 1000.0

        # 7. Asynchronously Update Redis, MongoDB, and Broadcast Events
        if episode:
            if new_state == AnomalyState.NORMAL and became_cleared:
                asyncio.create_task(anomaly_redis_state.clear_active_anomaly(window.tourist_id))
            else:
                asyncio.create_task(anomaly_redis_state.update_active_anomaly(episode))

            asyncio.create_task(anomaly_persistence.upsert_anomaly_episode(episode))

        if detected_evt:
            asyncio.create_task(self._broadcast_anomaly_detected(detected_evt))

        if cleared_evt:
            asyncio.create_task(self._broadcast_anomaly_cleared(cleared_evt))

        # Asynchronously evaluate candidate model in Shadow mode if enabled
        if shadow_engine.active_shadow_version:
            asyncio.create_task(
                shadow_engine.evaluate_shadow_window(
                    window=window,
                    production_score=score,
                    production_state=new_state.value,
                    production_version=model_ver,
                )
            )

        # Ingest Anomaly signal to Safety Orchestration Engine (Prompt 11)
        try:
            consec = episode.consecutive_windows if episode else (1 if new_state != AnomalyState.NORMAL else 0)
            anom_sig = SafetySignalFactory.create_anomaly_signal(
                tourist_id=window.tourist_id,
                session_id=window.session_id,
                state=new_state.value,
                score=score,
                threshold=thresh,
                consecutive_windows=consec,
                quality=quality_info.overall_quality,
                model_version=model_ver,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            asyncio.create_task(safety_orchestrator.ingest_signal(anom_sig))
        except Exception as se_err:
            logger.error(f"Safety orchestrator anomaly ingest error: {se_err}")

        # 8. Record Metrics
        latency_breakdown = ml_metrics_tracker.record_success(
            queue_wait_ms=queue_wait_ms,
            preprocessing_ms=preprocessing_ms,
            model_inference_ms=model_inference_ms,
            postprocessing_ms=postprocessing_ms,
            total_inference_ms=total_inference_ms,
        )

        return InferenceResult(
            window_id=window.window_id,
            tourist_id=window.tourist_id,
            session_id=window.session_id,
            model_version=model_ver,
            timestamp=datetime.now(timezone.utc).isoformat(),
            anomaly_score=score,
            threshold=thresh,
            state=new_state,
            quality=quality_info,
            latency=latency_breakdown,
            status=InferenceStatus.PROCESSED,
            reconstruction_mse=score,
        )

    async def _broadcast_anomaly_detected(self, payload: Any):
        """Broadcasts anomaly.detected to authority operations channels."""
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.ANOMALY_DETECTED.value,
            source="lstm_inference_service",
            payload=payload.model_dump() if hasattr(payload, "model_dump") else dict(payload),
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
            logger.info(f"Broadcasted 'anomaly.detected' for tourist {payload.tourist_id} to authority:operations")
        except Exception as e:
            logger.warning(f"Failed to publish anomaly.detected event: {e}")

    async def _broadcast_anomaly_cleared(self, payload: Any):
        """Broadcasts anomaly.cleared to authority operations channels."""
        envelope = RealtimeEventEnvelope(
            event_type=RealtimeEventType.ANOMALY_CLEARED.value,
            source="lstm_inference_service",
            payload=payload.model_dump() if hasattr(payload, "model_dump") else dict(payload),
        )
        try:
            await realtime_bus.publish_to_channel("authority:operations", envelope)
            logger.info(f"Broadcasted 'anomaly.cleared' for tourist {payload.tourist_id} to authority:operations")
        except Exception as e:
            logger.warning(f"Failed to publish anomaly.cleared event: {e}")

    def get_queue_depth(self) -> int:
        return self._queue.qsize()


ml_inference_engine = RealtimeInferenceEngine(queue_capacity=1000)
