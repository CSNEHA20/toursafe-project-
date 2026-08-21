"""
TourSafe ML Schemas and Data Contracts.
Defines ModelMetadata, InferenceResult, AnomalyEpisode, MLHealthResponse,
and realtime event payloads conforming to TourSafe system architecture.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class ModelHealthState(str, Enum):
    MODEL_LOADING = "MODEL_LOADING"
    MODEL_READY = "MODEL_READY"
    MODEL_DEGRADED = "MODEL_DEGRADED"
    MODEL_ERROR = "MODEL_ERROR"
    MODEL_DISABLED = "MODEL_DISABLED"


class AnomalyState(str, Enum):
    NORMAL = "normal"
    CANDIDATE = "candidate"
    ANOMALOUS = "anomalous"
    RECOVERING = "recovering"


class InferenceStatus(str, Enum):
    PROCESSED = "processed"
    SKIPPED = "skipped"
    FAILED = "failed"


class ModelMetadata(BaseModel):
    """
    Canonical Model Metadata Contract for Real-Time Inference.
    """
    model_version: str = Field(..., description="Semantic version of the model artifact (e.g. v1.0.0)")
    model_name: str = Field(default="TourSafeLSTMAutoencoder", description="Name of the model architecture")
    model_type: str = Field(default="lstm_autoencoder", description="Category of the ML model")
    framework: str = Field(default="pytorch_onnx", description="ML framework/runtime (e.g. pytorch, onnx)")
    framework_version: str = Field(default="1.17.0", description="Runtime framework version")
    input_timesteps: int = Field(default=150, description="Expected sequence length in samples (3s @ 50Hz)")
    input_channels: int = Field(default=8, description="Number of input feature channels")
    channel_order: List[str] = Field(
        default_factory=lambda: [
            "accel_x", "accel_y", "accel_z",
            "gyro_x", "gyro_y", "gyro_z",
            "accel_mag", "gyro_mag"
        ],
        description="Exact ordering of feature channels"
    )
    sampling_rate_hz: float = Field(default=50.0, description="Nominal sampling frequency in Hz")
    window_seconds: float = Field(default=3.0, description="Window temporal duration in seconds")
    window_stride_seconds: float = Field(default=1.0, description="Sliding window stride in seconds")
    normalization_version: str = Field(default="robust_iqr_v1", description="Normalization method and version")
    training_dataset_version: str = Field(default="uci_har_synth_v1", description="Dataset identifier used for training")
    primary_threshold: float = Field(default=5.804714, description="Calibrated anomaly decision threshold")
    warning_threshold: float = Field(default=4.934007, description="Calibrated recovery/warning threshold")
    critical_threshold: float = Field(default=7.546128, description="High-confidence critical anomaly threshold")
    threshold_method: str = Field(default="percentile_99", description="Calibration methodology")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    experiment_id: Optional[str] = Field(default=None)
    status: str = Field(default="production_candidate", description="Model deployment lifecycle status")


class InferenceQualityInfo(BaseModel):
    overall_quality: str = "good"
    gps_quality: str = "unavailable"
    imu_quality: str = "good"
    observed_frequency_hz: float = 50.0
    completeness_ratio: float = 1.0


class InferenceLatencyBreakdown(BaseModel):
    queue_wait_ms: float = 0.0
    preprocessing_ms: float = 0.0
    model_inference_ms: float = 0.0
    postprocessing_ms: float = 0.0
    total_inference_ms: float = 0.0


class InferenceResult(BaseModel):
    """
    Contract for individual window inference output.
    """
    inference_id: str = Field(default_factory=lambda: f"inf_{uuid.uuid4().hex[:12]}")
    window_id: str
    tourist_id: str
    session_id: str
    model_version: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    anomaly_score: Optional[float] = None
    threshold: float
    state: AnomalyState = AnomalyState.NORMAL
    quality: InferenceQualityInfo = Field(default_factory=InferenceQualityInfo)
    latency: InferenceLatencyBreakdown = Field(default_factory=InferenceLatencyBreakdown)
    status: InferenceStatus = InferenceStatus.PROCESSED
    reason: Optional[str] = None
    reconstruction_mse: Optional[float] = None


class AnomalyEpisode(BaseModel):
    """
    Persistent document representing a sustained anomaly episode.
    """
    anomaly_id: str = Field(default_factory=lambda: f"anom_{uuid.uuid4().hex[:12]}")
    tourist_id: str
    session_id: str
    model_version: str
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    cleared_at: Optional[str] = None
    status: str = Field(default="active", description="active | resolved")
    current_score: float = 0.0
    peak_score: float = 0.0
    threshold: float = 5.804714
    window_count: int = 1
    duration_seconds: float = 0.0
    quality: Dict[str, Any] = Field(default_factory=dict)
    last_known_gps: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AnomalyDetectedEventPayload(BaseModel):
    """
    Payload for anomaly.detected event emitted over realtime bus to authorities.
    """
    anomaly_id: str
    tourist_id: str
    session_id: str
    model_version: str
    timestamp: str
    window_start: str
    window_end: str
    anomaly_score: float
    threshold: float
    persistence_count: int
    quality: Dict[str, Any] = Field(default_factory=dict)
    last_known_gps: Optional[Dict[str, Any]] = None
    source: str = "lstm_inference_service"


class AnomalyClearedEventPayload(BaseModel):
    """
    Payload for anomaly.cleared event emitted over realtime bus to authorities.
    """
    anomaly_id: str
    tourist_id: str
    session_id: str
    model_version: str
    timestamp: str
    duration_seconds: float
    peak_score: float
    recovery_score: float
    threshold: float
    source: str = "lstm_inference_service"


class MLHealthResponse(BaseModel):
    """
    Health check and observability response for the ML inference service.
    """
    model_health: ModelHealthState
    model_version: str
    artifact_status: str
    preprocessing_status: str
    threshold_status: str
    runtime_framework: str
    device: str
    last_successful_inference: Optional[str] = None
    last_failed_inference: Optional[str] = None
    consecutive_failures: int = 0
    total_inferences: int = 0
    dropped_windows: int = 0
    skipped_windows: int = 0
    queue_depth: int = 0
    queue_capacity: int = 1000
    inference_rate_sec: float = 0.0
    error_rate: float = 0.0
    average_latency_ms: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
