"""
TourSafe ML Data Engineering & Model Lifecycle Schemas.
Defines data models, contracts, and enums for dataset versioning, data quality,
training configurations, experiment lineage, model registry lifecycle states,
approvals, deployment strategies (staging, shadow, canary, production),
rollback audits, and feature/model drift detection.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DatasetStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    READY_FOR_TRAINING = "READY_FOR_TRAINING"
    ARCHIVED = "ARCHIVED"


class ModelLifecycleStatus(str, Enum):
    TRAINED = "TRAINED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    STAGING = "STAGING"
    SHADOW = "SHADOW"
    CANARY = "CANARY"
    PRODUCTION = "PRODUCTION"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"
    ROLLED_BACK = "ROLLED_BACK"


class TrainingJobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DriftStatus(str, Enum):
    NORMAL = "NORMAL"          # PSI < 0.1
    DRIFTING = "DRIFTING"      # 0.1 <= PSI < 0.25
    CRITICAL = "CRITICAL"      # PSI >= 0.25
    UNKNOWN = "UNKNOWN"


class LabelStrategy(str, Enum):
    UNLABELED_NORMAL = "UNLABELED_NORMAL"
    LABELED_ANOMALY = "LABELED_ANOMALY"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Dataset & Data Validation Schemas
# ---------------------------------------------------------------------------

class DataQualitySummary(BaseModel):
    total_samples_inspected: int = 0
    valid_samples_count: int = 0
    invalid_samples_count: int = 0
    removed_samples_count: int = 0
    missing_fields_count: int = 0
    sequence_gaps_count: int = 0
    timestamp_jitter_count: int = 0
    duplicate_samples_count: int = 0
    nan_inf_count: int = 0
    session_count: int = 0
    subject_count: int = 0
    mean_sampling_rate_hz: float = 50.0
    sampling_rate_std_hz: float = 0.0
    completeness_ratio: float = 1.0
    passed_validation: bool = True
    rejection_reasons: List[str] = Field(default_factory=list)


class FeatureChannelDistribution(BaseModel):
    channel: str
    count: int
    mean: float
    std: float
    min: float
    p01: float
    p05: float
    p25: float
    median: float
    p75: float
    p95: float
    p99: float
    max: float
    missing_count: int = 0


class DatasetSplitSummary(BaseModel):
    split_name: str
    window_count: int
    subject_count: int
    subject_ids: List[str]
    session_count: int
    session_ids: List[str]
    normal_windows: int
    anomaly_windows: int


class DatasetRegistryEntry(BaseModel):
    dataset_id: str = Field(default_factory=lambda: f"ds_{uuid.uuid4().hex[:12]}")
    dataset_version: str = Field(..., description="e.g. dataset_v1")
    description: str = ""
    feature_version: str = "features_v1"
    status: DatasetStatus = DatasetStatus.CREATED
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "system"
    source_time_range_start: Optional[str] = None
    source_time_range_end: Optional[str] = None
    total_raw_records: int = 0
    total_windows: int = 0
    window_duration_seconds: float = 3.0
    window_stride_seconds: float = 1.0
    nominal_frequency_hz: float = 50.0
    splits: Dict[str, DatasetSplitSummary] = Field(default_factory=dict)
    quality_report: DataQualitySummary = Field(default_factory=DataQualitySummary)
    feature_distributions: Dict[str, FeatureChannelDistribution] = Field(default_factory=dict)
    artifact_path: Optional[str] = None
    sha256_hash: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DatasetBuildRequest(BaseModel):
    dataset_version: str = Field(..., description="Unique dataset identifier, e.g. dataset_v2")
    description: Optional[str] = None
    feature_version: str = "features_v1"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    session_ids: Optional[List[str]] = None
    quality_threshold: float = 0.6
    window_duration_seconds: float = 3.0
    window_stride_seconds: float = 1.0
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    test_ratio: float = 0.15


# ---------------------------------------------------------------------------
# Training & Experiment Schemas
# ---------------------------------------------------------------------------

class MLTrainingHyperparameters(BaseModel):
    learning_rate: float = 1e-3
    batch_size: int = 32
    epochs: int = 30
    hidden_dims: List[int] = Field(default_factory=lambda: [64, 32])
    latent_dim: int = 32
    dropout: float = 0.1
    clip_grad_norm: float = 1.0
    weight_decay: float = 1e-5
    early_stopping_patience: int = 8
    lr_reduce_patience: int = 4
    lr_reduce_factor: float = 0.5
    optimizer: str = "adam"
    loss_function: str = "mse"
    random_seed: int = 42
    device: str = "cpu"


class TrainingJobRecord(BaseModel):
    job_id: str = Field(default_factory=lambda: f"job_{uuid.uuid4().hex[:12]}")
    model_version: str = Field(..., description="Target model version, e.g. lstm-anomaly-v2")
    dataset_version: str = Field(..., description="Dataset version to train on")
    feature_version: str = "features_v1"
    status: TrainingJobStatus = TrainingJobStatus.QUEUED
    hyperparameters: MLTrainingHyperparameters = Field(default_factory=MLTrainingHyperparameters)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    created_by: str = "system"
    current_epoch: int = 0
    total_epochs: int = 30
    train_loss_history: List[float] = Field(default_factory=list)
    val_loss_history: List[float] = Field(default_factory=list)
    best_val_loss: Optional[float] = None
    best_epoch: Optional[int] = None
    error_message: Optional[str] = None
    experiment_id: Optional[str] = None
    logs: List[str] = Field(default_factory=list)


class ExperimentRecord(BaseModel):
    experiment_id: str = Field(default_factory=lambda: f"exp_{uuid.uuid4().hex[:12]}")
    name: str = ""
    model_version: str
    dataset_version: str
    feature_version: str
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    thresholds: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: float = 0.0
    hardware_info: Dict[str, Any] = Field(default_factory=dict)
    code_version: str = "Prompt 16 - ML Lifecycle"
    python_version: str = ""
    framework_version: str = ""
    random_seed: int = 42


# ---------------------------------------------------------------------------
# Model Registry & Governance Schemas
# ---------------------------------------------------------------------------

class ModelEvaluationMetrics(BaseModel):
    roc_auc: Optional[float] = None
    pr_auc: Optional[float] = None
    f1_score: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    specificity: Optional[float] = None
    false_positive_rate: Optional[float] = None
    false_negative_rate: Optional[float] = None
    confusion_matrix: Dict[str, int] = Field(default_factory=dict)
    reconstruction_mse_mean: float = 0.0
    reconstruction_mse_std: float = 0.0
    p95_reconstruction_error: float = 0.0
    p99_reconstruction_error: float = 0.0
    mean_inference_latency_ms: float = 0.0
    p95_inference_latency_ms: float = 0.0
    has_ground_truth: bool = False
    evaluation_dataset_version: str = ""


class ModelThresholdConfiguration(BaseModel):
    primary_threshold: float = 5.804714
    warning_threshold: float = 4.934007
    critical_threshold: float = 7.546128
    calibration_method: str = "percentile_99"
    calibration_dataset_version: str = ""
    calibrated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tuning_metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelValidationCheckResult(BaseModel):
    check_name: str
    passed: bool
    details: str


class ModelValidationGateResult(BaseModel):
    model_version: str
    validated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    passed_all_gates: bool
    checks: List[ModelValidationCheckResult] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class ModelApprovalRecord(BaseModel):
    approved_by: str
    approved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reason: str
    evaluation_summary: Dict[str, Any] = Field(default_factory=dict)


class DeploymentAuditRecord(BaseModel):
    audit_id: str = Field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:12]}")
    model_version: str
    previous_model_version: Optional[str] = None
    action: str  # STAGE, SHADOW, CANARY, DEPLOY_PRODUCTION, ROLLBACK
    deployed_by: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    environment: str = "production"
    reason: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ModelRegistryEntry(BaseModel):
    model_id: str = Field(default_factory=lambda: f"mod_{uuid.uuid4().hex[:12]}")
    model_version: str = Field(..., description="Immutable semantic version, e.g. lstm-anomaly-v1")
    model_name: str = "TourSafeLSTMAutoencoder"
    architecture_version: str = "lstm_ae_v1"
    feature_version: str = "features_v1"
    dataset_version: str = Field(..., description="Dataset used for training")
    training_config_version: str = "default_v1"
    code_version: str = "1.0.0"
    status: ModelLifecycleStatus = ModelLifecycleStatus.TRAINED
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "system"
    approval: Optional[ModelApprovalRecord] = None
    validation_gate: Optional[ModelValidationGateResult] = None
    metrics: ModelEvaluationMetrics = Field(default_factory=ModelEvaluationMetrics)
    threshold_config: ModelThresholdConfiguration = Field(default_factory=ModelThresholdConfiguration)
    artifact_location: str = ""
    sha256_hash: Optional[str] = None
    is_production: bool = False
    is_shadow: bool = False
    is_staging: bool = False
    is_canary: bool = False
    canary_percentage: float = 0.0
    deployment_history: List[DeploymentAuditRecord] = Field(default_factory=list)
    rollback_history: List[DeploymentAuditRecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Model Comparison & Drift Schemas
# ---------------------------------------------------------------------------

class MetricComparisonItem(BaseModel):
    metric_name: str
    production_value: Optional[float]
    candidate_value: Optional[float]
    difference: Optional[float]
    candidate_is_better: Optional[bool]
    requires_ground_truth: bool = False


class ModelComparisonReport(BaseModel):
    production_model_version: str
    candidate_model_version: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dataset_used: str
    has_ground_truth_labels: bool
    metrics_comparison: List[MetricComparisonItem] = Field(default_factory=list)
    reconstruction_distribution_diff: Dict[str, Any] = Field(default_factory=dict)
    operational_alert_rate_diff: Dict[str, Any] = Field(default_factory=dict)
    latency_comparison: Dict[str, Any] = Field(default_factory=dict)
    recommendation_summary: str
    approval_readiness: bool


class FeatureDriftMetric(BaseModel):
    feature_name: str
    psi_score: float
    ks_statistic: float
    ks_p_value: float
    status: DriftStatus
    training_mean: float
    current_mean: float
    training_std: float
    current_std: float
    details: str = ""


class ModelDriftReport(BaseModel):
    report_id: str = Field(default_factory=lambda: f"drift_{uuid.uuid4().hex[:12]}")
    model_version: str
    feature_version: str
    evaluated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    window_count_evaluated: int
    overall_drift_status: DriftStatus
    max_psi_score: float
    feature_drifts: List[FeatureDriftMetric] = Field(default_factory=list)
    concept_drift_status: str = "CONCEPT DRIFT NOT MEASURABLE (NO VERIFIED REAL-TIME GROUND TRUTH)"
    retraining_recommended: bool = False
    retraining_reason: Optional[str] = None


class ShadowInferenceMetric(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    window_id: str
    production_model_version: str
    candidate_model_version: str
    production_score: float
    candidate_score: float
    production_state: str
    candidate_state: str
    production_latency_ms: float
    candidate_latency_ms: float
    score_difference: float
    prediction_agreement: bool
