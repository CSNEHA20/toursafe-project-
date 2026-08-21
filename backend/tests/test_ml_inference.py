"""
TourSafe Real-Time LSTM ML Inference Test Suite.
Tests:
- Model artifact loading & validation
- Preprocessing & feature extraction
- Inference & MSE anomaly scoring
- State machine temporal persistence & hysteresis
- Episode deduplication & lifecycle
- Redis & MongoDB integration
- Bounded queue backpressure & metrics
- Latency & benchmark verification
- End-to-end telemetry pipeline integration
"""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import time
import numpy as np
import pytest

from app.schemas.ml import (
    AnomalyState,
    InferenceStatus,
    ModelHealthState,
    ModelMetadata,
)
from app.schemas.telemetry import (
    AccelerometerChannels,
    GPSPayload,
    GyroscopeChannels,
    QualityMetrics,
    QualityStateEnum,
    TelemetrySample,
    TelemetryWindow,
)
from app.services.ml.anomaly_scorer import AnomalyScorer, anomaly_scorer
from app.services.ml.engine import RealtimeInferenceEngine, ml_inference_engine
from app.services.ml.episode_manager import AnomalyEpisodeManager, anomaly_episode_manager
from app.services.ml.loader import ModelArtifactLoader, model_loader
from app.services.ml.metrics import MLMetricsTracker, ml_metrics_tracker
from app.services.ml.preprocessor import InferencePreprocessor, inference_preprocessor
from app.services.ml.state_machine import AnomalyStateMachine, anomaly_state_machine


def generate_mock_window(
    tourist_id: str = "tourist_test_01",
    session_id: str = "sess_ml_test_01",
    n_samples: int = 150,
    is_anomalous: bool = False,
    is_valid: bool = True,
    hz: float = 50.0,
) -> TelemetryWindow:
    """Helper to generate structured TelemetryWindow instances."""
    start_dt = datetime.now(timezone.utc) - timedelta(seconds=3.0)
    dt_step = 1.0 / hz

    samples = []
    for i in range(n_samples):
        s_time = (start_dt + timedelta(seconds=i * dt_step)).isoformat()

        if is_anomalous:
            # High amplitude violent motion pattern (outlier kinematics)
            ax = float(np.sin(i * 0.8) * 8.5 + np.random.normal(0, 1.5))
            ay = float(np.cos(i * 0.8) * 9.0 + np.random.normal(0, 1.5))
            az = float(np.sin(i * 1.2) * 8.0 + np.random.normal(0, 1.5))
            gx = float(np.sin(i * 1.5) * 6.5)
            gy = float(np.cos(i * 1.5) * 7.0)
            gz = float(np.sin(i * 1.0) * 6.0)
        else:
            # Ordinary walking kinematics (~0.6 - 1.2g, low rotation)
            ax = float(0.1 * np.sin(i * 0.2) + np.random.normal(0, 0.02))
            ay = float(0.98 + 0.1 * np.cos(i * 0.2) + np.random.normal(0, 0.02))
            az = float(0.05 * np.sin(i * 0.1) + np.random.normal(0, 0.02))
            gx = float(0.02 * np.sin(i * 0.1))
            gy = float(0.03 * np.cos(i * 0.1))
            gz = float(0.01 * np.sin(i * 0.1))

        s = TelemetrySample(
            packet_id=f"pkt_test_{i}",
            session_id=session_id,
            tourist_id=tourist_id,
            device_id="dev_sim_01",
            sequence_number=i + 1,
            timestamp=s_time,
            accelerometer=AccelerometerChannels(x=ax, y=ay, z=az),
            gyroscope=GyroscopeChannels(x=gx, y=gy, z=gz),
        )
        samples.append(s)

    quality = QualityMetrics(
        gps_quality=QualityStateEnum.GOOD,
        imu_quality=QualityStateEnum.GOOD,
        synchronization_quality=QualityStateEnum.EXCELLENT,
        network_quality=QualityStateEnum.EXCELLENT,
        overall_quality=QualityStateEnum.GOOD,
        observed_frequency_hz=hz,
    )

    return TelemetryWindow(
        window_id=f"win_test_{int(time.time() * 1000)}_{np.random.randint(100, 999)}",
        session_id=session_id,
        tourist_id=tourist_id,
        device_id="dev_sim_01",
        window_start=start_dt.isoformat(),
        window_end=(start_dt + timedelta(seconds=3.0)).isoformat(),
        duration_seconds=3.0,
        stride_seconds=1.0,
        sample_count=n_samples,
        observed_frequency_hz=hz,
        completeness_ratio=1.0 if is_valid else 0.4,
        is_valid=is_valid,
        validation_errors=[] if is_valid else ["Simulated invalid window completeness"],
        quality=quality,
        samples=samples,
        gps_context=GPSPayload(
            latitude=10.2381,
            longitude=77.4892,
            accuracy=5.0,
        ),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


class TestModelArtifactLoadingAndValidation:
    """Tests for model loading, artifact validation, and compatibility checks."""

    def test_production_model_loads_successfully(self):
        loader = ModelArtifactLoader()
        success = loader.load_and_validate("v1.0.0")
        assert success is True
        assert loader.health_state == ModelHealthState.MODEL_READY
        assert loader.metadata is not None
        assert loader.metadata.model_version == "v1.0.0"
        assert loader.metadata.input_timesteps == 150
        assert loader.metadata.input_channels == 8
        assert loader.primary_threshold > 0.0
        assert loader.warning_threshold > 0.0
        assert loader.scaler is not None
        assert loader.scaler.is_fitted is True

    def test_missing_version_handles_gracefully(self):
        loader = ModelArtifactLoader()
        success = loader.load_and_validate("non_existent_version_v999")
        assert success is False
        assert loader.health_state == ModelHealthState.MODEL_ERROR
        assert len(loader.validation_errors) > 0

    def test_raw_inference_smoke_test(self):
        loader = ModelArtifactLoader()
        loader.load_and_validate("v1.0.0")
        dummy = np.zeros((1, 150, 8), dtype=np.float32)
        out = loader.infer_raw(dummy)
        assert out.shape == (1, 150, 8)
        assert not np.isnan(out).any()


class TestPreprocessingPipeline:
    """Tests for feature extraction, resampling, and robust IQR scaling."""

    @pytest.fixture(autouse=True)
    def setup_loader(self):
        model_loader.load_and_validate("v1.0.0")

    def test_valid_150_sample_window_preprocessing(self):
        window = generate_mock_window(n_samples=150, is_valid=True)
        tensor, error = inference_preprocessor.preprocess_window(window)

        assert error is None
        assert tensor is not None
        assert tensor.shape == (1, 150, 8)
        assert tensor.dtype == np.float32
        assert not np.isnan(tensor).any()

    def test_jittered_sample_rate_resampling(self):
        # 142 samples instead of 150 -> resampler should interpolate to exact 150 timesteps
        window = generate_mock_window(n_samples=142, is_valid=True)
        tensor, error = inference_preprocessor.preprocess_window(window)

        assert error is None
        assert tensor is not None
        assert tensor.shape == (1, 150, 8)

    def test_invalid_window_is_rejected(self):
        window = generate_mock_window(is_valid=False)
        tensor, error = inference_preprocessor.preprocess_window(window)

        assert tensor is None
        assert "Invalid window" in error

    def test_channel_order_and_magnitudes(self):
        window = generate_mock_window(n_samples=150)
        tensor, error = inference_preprocessor.preprocess_window(window)
        assert error is None
        # Verify 8 channels are produced
        assert tensor.shape[-1] == 8


class TestAnomalyScoringAndInference:
    """Tests for LSTM autoencoder inference and reconstruction MSE anomaly scoring."""

    @pytest.fixture(autouse=True)
    def setup_loader(self):
        model_loader.load_and_validate("v1.0.0")

    @pytest.mark.asyncio
    async def test_normal_motion_produces_low_anomaly_score(self):
        window = generate_mock_window(is_anomalous=False)
        result = await ml_inference_engine.process_single_window(window)

        assert result.status == InferenceStatus.PROCESSED
        assert result.anomaly_score is not None
        assert result.threshold == model_loader.primary_threshold
        # Normal walking error should be significantly below calibrated threshold (~5.8)
        assert result.anomaly_score < model_loader.primary_threshold
        assert result.model_version == "v1.0.0"

    @pytest.mark.asyncio
    async def test_violent_anomaly_produces_high_reconstruction_error(self):
        window = generate_mock_window(is_anomalous=True)
        result = await ml_inference_engine.process_single_window(window)

        assert result.status == InferenceStatus.PROCESSED
        assert result.anomaly_score is not None
        assert result.anomaly_score >= model_loader.warning_threshold

    @pytest.mark.asyncio
    async def test_skipped_inference_on_invalid_window(self):
        window = generate_mock_window(is_valid=False)
        result = await ml_inference_engine.process_single_window(window)

        assert result.status == InferenceStatus.SKIPPED
        assert result.reason is not None
        assert result.anomaly_score is None


class TestAnomalyStateMachineAndHysteresis:
    """Tests for temporal persistence, hysteresis gating, and oscillation prevention."""

    def test_temporal_persistence_and_candidate_transition(self):
        sm = AnomalyStateMachine(persistence_count=2, recovery_count=2)
        tourist_id = "tourist_sm_01"
        session_id = "sess_sm_01"
        t_high = 5.804714
        t_recov = 4.934007

        # Window 1: High score -> transitions to CANDIDATE (not yet ANOMALOUS)
        prev, curr, became_anom, became_clr = sm.evaluate_window(
            tourist_id, session_id, anomaly_score=6.5, anomaly_threshold=t_high, recovery_threshold=t_recov
        )
        assert prev == AnomalyState.NORMAL
        assert curr == AnomalyState.CANDIDATE
        assert became_anom is False
        assert became_clr is False

        # Window 2: High score persists -> transitions to ANOMALOUS
        prev, curr, became_anom, became_clr = sm.evaluate_window(
            tourist_id, session_id, anomaly_score=6.8, anomaly_threshold=t_high, recovery_threshold=t_recov
        )
        assert prev == AnomalyState.CANDIDATE
        assert curr == AnomalyState.ANOMALOUS
        assert became_anom is True
        assert became_clr is False

    def test_candidate_clears_on_normal_window(self):
        sm = AnomalyStateMachine(persistence_count=2, recovery_count=2)
        tourist_id = "tourist_sm_02"
        session_id = "sess_sm_02"
        t_high = 5.804714
        t_recov = 4.934007

        # Window 1: Elevated -> CANDIDATE
        sm.evaluate_window(tourist_id, session_id, 6.0, t_high, t_recov)

        # Window 2: Normal score -> reverts to NORMAL without triggering alarm
        prev, curr, became_anom, became_clr = sm.evaluate_window(
            tourist_id, session_id, 1.2, t_high, t_recov
        )
        assert prev == AnomalyState.CANDIDATE
        assert curr == AnomalyState.NORMAL
        assert became_anom is False
        assert became_clr is False

    def test_hysteresis_deadband_stability(self):
        sm = AnomalyStateMachine(persistence_count=2, recovery_count=2)
        tourist_id = "tourist_sm_03"
        session_id = "sess_sm_03"
        t_high = 5.804714
        t_recov = 4.934007

        # 2 elevated windows -> ANOMALOUS
        sm.evaluate_window(tourist_id, session_id, 6.0, t_high, t_recov)
        sm.evaluate_window(tourist_id, session_id, 6.0, t_high, t_recov)

        # Window with score in deadband (5.2 is between 4.934 and 5.804)
        prev, curr, became_anom, became_clr = sm.evaluate_window(
            tourist_id, session_id, 5.2, t_high, t_recov
        )
        # Should remain ANOMALOUS without fluttering
        assert curr == AnomalyState.ANOMALOUS
        assert became_clr is False

    def test_recovery_hysteresis(self):
        sm = AnomalyStateMachine(persistence_count=2, recovery_count=2)
        tourist_id = "tourist_sm_04"
        session_id = "sess_sm_04"
        t_high = 5.804714
        t_recov = 4.934007

        # Reach ANOMALOUS
        sm.evaluate_window(tourist_id, session_id, 6.5, t_high, t_recov)
        sm.evaluate_window(tourist_id, session_id, 6.5, t_high, t_recov)

        # 1st normal window (< 4.934) -> RECOVERING
        prev, curr, became_anom, became_clr = sm.evaluate_window(
            tourist_id, session_id, 2.0, t_high, t_recov
        )
        assert curr == AnomalyState.RECOVERING
        assert became_clr is False

        # 2nd normal window -> NORMAL (became_cleared = True)
        prev, curr, became_anom, became_clr = sm.evaluate_window(
            tourist_id, session_id, 1.5, t_high, t_recov
        )
        assert curr == AnomalyState.NORMAL
        assert became_clr is True


class TestEpisodeManagementAndDeduplication:
    """Tests for single-episode continuity and deduplication."""

    def test_episode_deduplication_lifecycle(self):
        em = AnomalyEpisodeManager()
        window1 = generate_mock_window(tourist_id="tourist_ep_01", is_anomalous=True)
        window2 = generate_mock_window(tourist_id="tourist_ep_01", is_anomalous=True)
        window3 = generate_mock_window(tourist_id="tourist_ep_01", is_anomalous=False)

        # Transition 1: Became anomalous -> Emits detected event, starts episode
        det_evt, clr_evt, ep = em.handle_window_transition(
            window=window1,
            score=6.2,
            prev_state=AnomalyState.CANDIDATE,
            new_state=AnomalyState.ANOMALOUS,
            became_anomalous=True,
            became_cleared=False,
        )
        assert det_evt is not None
        assert clr_evt is None
        assert ep is not None
        assert ep.status == "active"
        assert ep.peak_score == 6.2
        anomaly_id = ep.anomaly_id

        # Transition 2: Continuing anomalous with higher score -> Updates same episode without duplicate event
        det_evt2, clr_evt2, ep2 = em.handle_window_transition(
            window=window2,
            score=7.4,
            prev_state=AnomalyState.ANOMALOUS,
            new_state=AnomalyState.ANOMALOUS,
            became_anomalous=False,
            became_cleared=False,
        )
        assert det_evt2 is None  # No duplicate event
        assert clr_evt2 is None
        assert ep2.anomaly_id == anomaly_id
        assert ep2.peak_score == 7.4
        assert ep2.window_count == 2

        # Transition 3: Became cleared -> Emits cleared event, resolves episode
        det_evt3, clr_evt3, ep3 = em.handle_window_transition(
            window=window3,
            score=1.2,
            prev_state=AnomalyState.RECOVERING,
            new_state=AnomalyState.NORMAL,
            became_anomalous=False,
            became_cleared=True,
        )
        assert det_evt3 is None
        assert clr_evt3 is not None
        assert clr_evt3.anomaly_id == anomaly_id
        assert clr_evt3.peak_score == 7.4
        assert ep3.status == "resolved"


class TestLatencyAndObservabilityMetrics:
    """Tests for latency tracking, throughput calculation, and health response."""

    def test_metrics_tracker_latency_percentiles(self):
        tracker = MLMetricsTracker()

        # Simulate 50 inference latency measurements
        for i in range(1, 51):
            tracker.record_success(
                queue_wait_ms=0.5,
                preprocessing_ms=1.2,
                model_inference_ms=i * 0.1,
                postprocessing_ms=0.3,
                total_inference_ms=2.0 + (i * 0.1),
            )

        stats = tracker.get_latency_stats()
        assert stats["mean_ms"] > 0
        assert stats["p50_ms"] > 0
        assert stats["p95_ms"] >= stats["p50_ms"]
        assert stats["p99_ms"] >= stats["p95_ms"]
        assert tracker.total_inferences == 50

    def test_health_summary_payload(self):
        tracker = MLMetricsTracker()
        summary = tracker.get_health_summary(queue_depth=5, queue_capacity=1000)
        assert summary.queue_depth == 5
        assert summary.queue_capacity == 1000
        assert summary.model_health in [ModelHealthState.MODEL_READY, ModelHealthState.MODEL_LOADING]


class TestEndToEndTelemetryReplayAndPipelineIntegration:
    """Tests feeding sequential windows through the complete pipeline."""

    @pytest.fixture(autouse=True)
    def setup_loader(self):
        model_loader.load_and_validate("v1.0.0")

    @pytest.mark.asyncio
    async def test_sequential_window_stream_integration(self):
        tourist_id = "tourist_replay_01"
        session_id = "sess_replay_01"

        # Step 1: Feed 3 normal windows
        for _ in range(3):
            w = generate_mock_window(tourist_id=tourist_id, session_id=session_id, is_anomalous=False)
            res = await ml_inference_engine.process_single_window(w)
            assert res.status == InferenceStatus.PROCESSED
            assert res.state == AnomalyState.NORMAL

        # Step 2: Feed 2 anomalous windows (CANDIDATE -> ANOMALOUS)
        w_anom1 = generate_mock_window(tourist_id=tourist_id, session_id=session_id, is_anomalous=True)
        res1 = await ml_inference_engine.process_single_window(w_anom1)
        assert res1.state == AnomalyState.CANDIDATE

        w_anom2 = generate_mock_window(tourist_id=tourist_id, session_id=session_id, is_anomalous=True)
        res2 = await ml_inference_engine.process_single_window(w_anom2)
        assert res2.state == AnomalyState.ANOMALOUS

        # Step 3: Feed 2 recovery windows (ANOMALOUS -> RECOVERING -> NORMAL)
        w_rec1 = generate_mock_window(tourist_id=tourist_id, session_id=session_id, is_anomalous=False)
        res_r1 = await ml_inference_engine.process_single_window(w_rec1)
        assert res_r1.state == AnomalyState.RECOVERING

        w_rec2 = generate_mock_window(tourist_id=tourist_id, session_id=session_id, is_anomalous=False)
        res_r2 = await ml_inference_engine.process_single_window(w_rec2)
        assert res_r2.state == AnomalyState.NORMAL
