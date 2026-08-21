"""
TourSafe ML Observability & Latency Tracking Engine.
Tracks real-time latency percentiles (mean, p50, p95, p99), throughput rates,
queue backpressure, and model health diagnostics.
"""

from collections import deque
from datetime import datetime, timezone
import time
from typing import Deque, Dict, List, Optional
import numpy as np

from ...schemas.ml import InferenceLatencyBreakdown, MLHealthResponse, ModelHealthState
from .loader import model_loader


class MLMetricsTracker:
    """
    In-memory rolling metrics collector for ML inference.
    """

    def __init__(self, max_history_size: int = 1000):
        self.max_history_size = max_history_size
        self.latency_history: Deque[float] = deque(maxlen=max_history_size)
        self.preprocess_history: Deque[float] = deque(maxlen=max_history_size)
        self.inference_history: Deque[float] = deque(maxlen=max_history_size)
        self.queue_wait_history: Deque[float] = deque(maxlen=max_history_size)

        self.total_inferences: int = 0
        self.total_failures: int = 0
        self.consecutive_failures: int = 0
        self.dropped_windows: int = 0
        self.skipped_windows: int = 0

        self.last_successful_inference: Optional[str] = None
        self.last_failed_inference: Optional[str] = None
        self.last_error_message: Optional[str] = None

        self._start_time: float = time.time()
        self._window_timestamps: Deque[float] = deque(maxlen=100)

    def record_success(
        self,
        queue_wait_ms: float,
        preprocessing_ms: float,
        model_inference_ms: float,
        postprocessing_ms: float,
        total_inference_ms: float,
    ) -> InferenceLatencyBreakdown:
        now_dt = datetime.now(timezone.utc).isoformat()
        now_sec = time.time()

        self.total_inferences += 1
        self.consecutive_failures = 0
        self.last_successful_inference = now_dt
        self._window_timestamps.append(now_sec)

        self.queue_wait_history.append(queue_wait_ms)
        self.preprocess_history.append(preprocessing_ms)
        self.inference_history.append(model_inference_ms)
        self.latency_history.append(total_inference_ms)

        return InferenceLatencyBreakdown(
            queue_wait_ms=round(queue_wait_ms, 2),
            preprocessing_ms=round(preprocessing_ms, 2),
            model_inference_ms=round(model_inference_ms, 2),
            postprocessing_ms=round(postprocessing_ms, 2),
            total_inference_ms=round(total_inference_ms, 2),
        )

    def record_failure(self, error_msg: str):
        now_dt = datetime.now(timezone.utc).isoformat()
        self.total_failures += 1
        self.consecutive_failures += 1
        self.last_failed_inference = now_dt
        self.last_error_message = error_msg

    def record_dropped_window(self):
        self.dropped_windows += 1

    def record_skipped_window(self):
        self.skipped_windows += 1

    def compute_throughput(self) -> float:
        """Computes current throughput (windows/second) over recent activity."""
        if len(self._window_timestamps) < 2:
            return 0.0
        time_span = self._window_timestamps[-1] - self._window_timestamps[0]
        if time_span <= 0:
            return 0.0
        return round((len(self._window_timestamps) - 1) / time_span, 2)

    def get_latency_stats(self) -> Dict[str, float]:
        """Calculates mean, p50, p95, and p99 from rolling latency history."""
        if not self.latency_history:
            return {
                "mean_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            }

        arr = np.array(self.latency_history, dtype=np.float32)
        return {
            "mean_ms": round(float(np.mean(arr)), 2),
            "p50_ms": round(float(np.percentile(arr, 50)), 2),
            "p95_ms": round(float(np.percentile(arr, 95)), 2),
            "p99_ms": round(float(np.percentile(arr, 99)), 2),
        }

    def get_health_summary(self, queue_depth: int, queue_capacity: int) -> MLHealthResponse:
        """Produces comprehensive health and performance diagnostic payload."""
        lat_stats = self.get_latency_stats()
        throughput = self.compute_throughput()
        total_eval = self.total_inferences + self.total_failures
        error_rate = round((self.total_failures / max(1, total_eval)), 4)

        return MLHealthResponse(
            model_health=model_loader.health_state,
            model_version=model_loader.metadata.model_version if model_loader.metadata else "unknown",
            artifact_status="valid" if model_loader.health_state == ModelHealthState.MODEL_READY else "error",
            preprocessing_status="ready" if model_loader.scaler is not None else "unavailable",
            threshold_status=f"primary={model_loader.primary_threshold:.4f}, recovery={model_loader.warning_threshold:.4f}",
            runtime_framework=model_loader.active_runtime,
            device=model_loader.device,
            last_successful_inference=self.last_successful_inference,
            last_failed_inference=self.last_failed_inference,
            consecutive_failures=self.consecutive_failures,
            total_inferences=self.total_inferences,
            dropped_windows=self.dropped_windows,
            skipped_windows=self.skipped_windows,
            queue_depth=queue_depth,
            queue_capacity=queue_capacity,
            inference_rate_sec=throughput,
            error_rate=error_rate,
            average_latency_ms=lat_stats["mean_ms"],
            latency_p50_ms=lat_stats["p50_ms"],
            latency_p95_ms=lat_stats["p95_ms"],
            latency_p99_ms=lat_stats["p99_ms"],
        )


ml_metrics_tracker = MLMetricsTracker()
