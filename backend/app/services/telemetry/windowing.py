import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from ...core.config import settings
from ...schemas.telemetry import (
    GPSPayload,
    QualityMetrics,
    QualityStateEnum,
    TelemetrySample,
    TelemetryWindow,
)
from .quality import quality_evaluator

logger = logging.getLogger("toursafe.telemetry.windowing")


class SessionWindowBuffer:
    """Buffer of recent samples and GPS context for a single telemetry session."""

    def __init__(self, session_id: str, tourist_id: str):
        self.session_id = session_id
        self.tourist_id = tourist_id
        self.samples: List[TelemetrySample] = []
        self.last_gps: Optional[GPSPayload] = None
        self.last_window_end_dt: Optional[datetime] = None

    def add_sample(self, sample: TelemetrySample):
        if sample.gps:
            self.last_gps = sample.gps
        if sample.accelerometer and sample.gyroscope:
            self.samples.append(sample)
            # Bound buffer memory to max ~1000 samples (~20 seconds of 50 Hz)
            if len(self.samples) > 1000:
                self.samples = self.samples[-800:]

    def clear(self):
        self.samples.clear()
        self.last_gps = None
        self.last_window_end_dt = None


class TelemetryWindowEngine:
    """
    Constructs and validates canonical 3-second temporal telemetry windows.
    Applies configurable stride, computes completeness ratio, validates monotonicity
    and maximum gap tolerances, and aligns GPS context without fabricating data.
    """

    def __init__(self):
        self._buffers: Dict[str, SessionWindowBuffer] = {}
        self._lock = asyncio.Lock()

    def _get_buffer(self, session_id: str, tourist_id: str) -> SessionWindowBuffer:
        if session_id not in self._buffers:
            self._buffers[session_id] = SessionWindowBuffer(session_id, tourist_id)
        return self._buffers[session_id]

    async def ingest_and_evaluate_windows(
        self,
        sample: TelemetrySample,
    ) -> List[TelemetryWindow]:
        """
        Feeds a sample into the session buffer and extracts any newly completed windows.
        """
        async with self._lock:
            buf = self._get_buffer(sample.session_id, sample.tourist_id)
            buf.add_sample(sample)

            return self.process_buffer(
                buf=buf,
                duration_sec=settings.telemetry_window_duration_sec,
                stride_sec=settings.telemetry_window_stride_sec,
                target_hz=settings.telemetry_nominal_frequency_hz,
                min_completeness=settings.telemetry_min_completeness_ratio,
                max_gap_ms=settings.telemetry_max_time_gap_ms,
            )

    @classmethod
    def process_buffer(
        cls,
        buf: SessionWindowBuffer,
        duration_sec: float = 3.0,
        stride_sec: float = 1.0,
        target_hz: float = 50.0,
        min_completeness: float = 0.6,
        max_gap_ms: float = 250.0,
    ) -> List[TelemetryWindow]:
        """
        Extracts all valid or evaluated windows from the buffered samples.
        """
        if len(buf.samples) < 10:
            return []

        # Sort samples by sensor timestamp to ensure true temporal sequence
        sorted_samples = sorted(
            buf.samples,
            key=lambda s: datetime.fromisoformat(s.timestamp.replace("Z", "+00:00")),
        )

        first_dt = datetime.fromisoformat(sorted_samples[0].timestamp.replace("Z", "+00:00"))
        last_dt = datetime.fromisoformat(sorted_samples[-1].timestamp.replace("Z", "+00:00"))

        total_span_sec = (last_dt - first_dt).total_seconds()
        if total_span_sec < duration_sec:
            return []

        windows: List[TelemetryWindow] = []

        # Determine sliding window start anchor
        if buf.last_window_end_dt is None:
            anchor_dt = first_dt
        else:
            # Advance by stride from previous window start
            anchor_dt = buf.last_window_end_dt - timedelta(seconds=(duration_sec - stride_sec))

        while True:
            window_end_dt = anchor_dt + timedelta(seconds=duration_sec)
            if window_end_dt > last_dt:
                break

            # Collect samples falling within [anchor_dt, window_end_dt]
            window_samples = [
                s for s in sorted_samples
                if anchor_dt <= datetime.fromisoformat(s.timestamp.replace("Z", "+00:00")) <= window_end_dt
            ]

            window = cls.validate_and_build_window(
                session_id=buf.session_id,
                tourist_id=buf.tourist_id,
                window_start_dt=anchor_dt,
                window_end_dt=window_end_dt,
                samples=window_samples,
                gps_context=buf.last_gps,
                duration_sec=duration_sec,
                stride_sec=stride_sec,
                target_hz=target_hz,
                min_completeness=min_completeness,
                max_gap_ms=max_gap_ms,
            )

            windows.append(window)
            buf.last_window_end_dt = window_end_dt
            anchor_dt = anchor_dt + timedelta(seconds=stride_sec)

        return windows

    @classmethod
    def validate_and_build_window(
        cls,
        session_id: str,
        tourist_id: str,
        window_start_dt: datetime,
        window_end_dt: datetime,
        samples: List[TelemetrySample],
        gps_context: Optional[GPSPayload] = None,
        duration_sec: float = 3.0,
        stride_sec: float = 1.0,
        target_hz: float = 50.0,
        min_completeness: float = 0.6,
        max_gap_ms: float = 250.0,
    ) -> TelemetryWindow:
        """
        Validates window criteria and builds canonical TelemetryWindow document.
        """
        sample_count = len(samples)
        expected_samples = target_hz * duration_sec
        completeness_ratio = round(sample_count / max(1.0, expected_samples), 4)

        validation_errors: List[str] = []
        is_valid = True

        # Calculate observed sampling frequency
        if sample_count >= 2:
            s_first_dt = datetime.fromisoformat(samples[0].timestamp.replace("Z", "+00:00"))
            s_last_dt = datetime.fromisoformat(samples[-1].timestamp.replace("Z", "+00:00"))
            span = max(0.001, (s_last_dt - s_first_dt).total_seconds())
            observed_hz = round((sample_count - 1) / span, 2)
        else:
            observed_hz = 0.0

        # Criterion 1: Completeness ratio
        if completeness_ratio < min_completeness:
            is_valid = False
            validation_errors.append(
                f"Sample completeness ({completeness_ratio:.2f}) below threshold ({min_completeness})"
            )

        # Criterion 2: Check timestamp monotonicity and maximum gap
        max_observed_gap_ms = 0.0
        for i in range(1, sample_count):
            t_prev = datetime.fromisoformat(samples[i - 1].timestamp.replace("Z", "+00:00"))
            t_curr = datetime.fromisoformat(samples[i].timestamp.replace("Z", "+00:00"))
            gap = (t_curr - t_prev).total_seconds() * 1000.0
            if gap < 0:
                is_valid = False
                validation_errors.append(f"Non-monotonic timestamp sequence at index {i}")
            if gap > max_observed_gap_ms:
                max_observed_gap_ms = gap

        if max_observed_gap_ms > max_gap_ms:
            is_valid = False
            validation_errors.append(
                f"Max inter-sample gap ({max_observed_gap_ms:.1f}ms) exceeded limit ({max_gap_ms}ms)"
            )

        # Criterion 3: Sampling frequency anomaly
        if sample_count > 10 and (observed_hz < 15.0 or observed_hz > 120.0):
            is_valid = False
            validation_errors.append(
                f"Observed sampling frequency ({observed_hz} Hz) deviates excessively from nominal {target_hz} Hz"
            )

        # Quality metrics
        quality = quality_evaluator.compute_metrics(
            gps_accuracy=gps_context.accuracy if gps_context else None,
            observed_imu_hz=observed_hz,
            target_hz=target_hz,
            sync_delta_ms=0.0,
            last_gap_duration_ms=max_observed_gap_ms,
        )

        return TelemetryWindow(
            window_id=f"win_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            tourist_id=tourist_id,
            device_id=samples[0].device_id if samples else None,
            window_start=window_start_dt.isoformat(),
            window_end=window_end_dt.isoformat(),
            duration_seconds=duration_sec,
            stride_seconds=stride_sec,
            sample_count=sample_count,
            observed_frequency_hz=observed_hz,
            completeness_ratio=completeness_ratio,
            is_valid=is_valid,
            validation_errors=validation_errors,
            quality=quality,
            samples=samples,
            gps_context=gps_context,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def remove_session(self, session_id: str):
        self._buffers.pop(session_id, None)


telemetry_window_engine = TelemetryWindowEngine()
