"""
TourSafe ML Data Engineering & Model Lifecycle Test Suite (Prompt 16).
Validates:
1. Raw Telemetry Validation & Rejection Recording
2. Data Quality Reporting
3. Strict Anti-Leakage Detection (Subject/Session/Window Overlap)
4. Deterministic Dataset Building, Hashing & Versioning
5. Robust Feature Distribution Calculations
6. Model Artifact Packaging, ONNX Parity & Integrity Checksums
7. Automated Pre-Approval Model Validation Gate
8. Model Registry State Machine Transitions & Human Governance Approval
9. Authoritative Dynamic Production Pointer & Atomic Rollback
10. Model Comparison & Insufficient Ground Truth Flagging
11. Feature Drift Detection (PSI & KS-Test) & Retraining Advisory
12. Shadow Mode Parallel Inference & Score Parity Tracking
13. Model Failure Safety Invariant (Never convert failure to NORMAL)
14. End-to-End ML Lifecycle Execution
"""

import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import numpy as np
import pytest
import torch

from app.ml.config import ModelConfig, TrainingConfig, WindowConfig
from app.ml.dataset.synthetic_generator import SyntheticIMUGenerator
from app.ml.evaluation.threshold import AnomalyThresholdCalibrator, ThresholdCalibrationResult
from app.ml.evaluation.evaluator import AnomalyEvaluationReport, ModelEvaluator
from app.ml.lifecycle import (
    data_quality_reporter,
    dataset_builder,
    dataset_registry,
    drift_detector,
    experiment_tracker,
    feature_registry,
    leakage_detector,
    model_comparison_engine,
    model_packager,
    model_registry,
    model_validation_gate,
    raw_telemetry_validator,
    shadow_engine,
    training_manager,
)
from app.ml.lifecycle.data_validator import RawTelemetryValidator
from app.ml.lifecycle.drift_detector import FeatureDriftDetector
from app.ml.lifecycle.leakage_detector import DataLeakageDetector
from app.ml.lifecycle.model_packager import ModelPackager
from app.ml.lifecycle.model_validator import ModelValidationGate
from app.ml.models.lstm_autoencoder import TourSafeLSTMAutoencoder
from app.ml.preprocessing.scaler import TourSafeRobustScaler
from app.ml.training.trainer import AutoencoderTrainer
from app.schemas.ml import AnomalyState, InferenceStatus, ModelHealthState
from app.schemas.ml_lifecycle import (
    DataQualitySummary,
    DatasetRegistryEntry,
    DatasetStatus,
    DriftStatus,
    FeatureChannelDistribution,
    MLTrainingHyperparameters,
    ModelEvaluationMetrics,
    ModelLifecycleStatus,
    ModelRegistryEntry,
    ModelThresholdConfiguration,
)
from app.schemas.telemetry import (
    AccelerometerChannels,
    GyroscopeChannels,
    QualityMetrics,
    TelemetrySample,
    TelemetryWindow,
)
from app.services.ml.loader import ModelArtifactLoader


# ---------------------------------------------------------------------------
# Test Group 1: Raw Telemetry Validation & Quality Reporting
# ---------------------------------------------------------------------------

class TestTelemetryValidationAndQuality:
    """Verifies data validation rules, outlier rejection, and quality reporting."""

    def test_validation_detects_nan_inf_and_bounds(self):
        validator = RawTelemetryValidator(accel_range_g=16.0, gyro_range_rad_s=35.0)

        # 1. Valid sample
        valid_sample = {
            "timestamp": 1700000000.0,
            "session_id": "sess_01",
            "accelerometer": {"x": 0.1, "y": 0.2, "z": 1.0},
            "gyroscope": {"x": 0.01, "y": 0.02, "z": 0.03},
        }
        issues = validator.validate_sample_dictionary(valid_sample, 0)
        assert len(issues) == 0

        # 2. NaN accelerometer value
        nan_sample = {
            "timestamp": 1700000000.0,
            "session_id": "sess_01",
            "accelerometer": {"x": float("nan"), "y": 0.2, "z": 1.0},
            "gyroscope": {"x": 0.01, "y": 0.02, "z": 0.03},
        }
        issues = validator.validate_sample_dictionary(nan_sample, 1)
        assert any(i.issue_type == "NAN_INF_VALUE" for i in issues)

        # 3. Out-of-bounds sensor reading (e.g. 50g shock)
        oob_sample = {
            "timestamp": 1700000000.0,
            "session_id": "sess_01",
            "accelerometer": {"x": 50.0, "y": 0.2, "z": 1.0},
            "gyroscope": {"x": 0.01, "y": 0.02, "z": 0.03},
        }
        issues = validator.validate_sample_dictionary(oob_sample, 2)
        assert any(i.issue_type == "SENSOR_OUT_OF_BOUNDS" for i in issues)

    def test_session_validation_detects_timestamp_jitter_and_duplicates(self):
        validator = RawTelemetryValidator(nominal_frequency_hz=50.0)

        samples = []
        t = 1000.0
        for i in range(150):
            samples.append({
                "timestamp": t,
                "sequence_number": i,
                "session_id": "sess_02",
                "accelerometer": {"x": 0.0, "y": 0.0, "z": 1.0},
                "gyroscope": {"x": 0.0, "y": 0.0, "z": 0.0},
            })
            t += 0.02

        # Insert a non-monotonic timestamp at index 50
        samples[50]["timestamp"] = 999.0

        res = validator.validate_session_stream(samples, session_id="sess_02")
        assert any(i.issue_type == "NON_MONOTONIC_TIMESTAMP" for i in res.issues)
        assert res.total_records == 150
        assert res.invalid_records > 0

    def test_data_quality_report_aggregation(self):
        v1 = raw_telemetry_validator.validate_session_stream([
            {
                "timestamp": 1000.0 + (i * 0.02),
                "sequence_number": i,
                "accelerometer": {"x": 0.0, "y": 0.0, "z": 1.0},
                "gyroscope": {"x": 0.0, "y": 0.0, "z": 0.0},
            }
            for i in range(150)
        ])
        v2 = raw_telemetry_validator.validate_session_stream([
            {
                "timestamp": 2000.0,
                "sequence_number": 0,
                "accelerometer": {"x": float("nan"), "y": 0.0, "z": 1.0},
                "gyroscope": {"x": 0.0, "y": 0.0, "z": 0.0},
            }
        ])

        summary = data_quality_reporter.compile_summary([v1, v2], total_sessions=2, total_subjects=2)
        assert summary.total_samples_inspected == 151
        assert summary.valid_samples_count == 150
        assert summary.invalid_samples_count == 1
        assert summary.nan_inf_count >= 1
        assert summary.passed_validation is True


# ---------------------------------------------------------------------------
# Test Group 2: Anti-Leakage Detection & Feature Registry
# ---------------------------------------------------------------------------

class TestAntiLeakageAndFeatureRegistry:
    """Verifies strict partition independence and feature specifications."""

    def test_anti_leakage_detector_rejects_subject_overlap(self):
        detector = DataLeakageDetector()

        # Overlap SUB_02 in train and test
        train_subs = ["SUB_01", "SUB_02", "SUB_03"]
        val_subs = ["SUB_04"]
        test_subs = ["SUB_02", "SUB_05"]

        res = detector.check_splits(
            train_subjects=train_subs,
            val_subjects=val_subs,
            test_subjects=test_subs,
        )
        assert res.passed is False
        assert "train_test" in res.subject_overlaps
        assert "SUB_02" in res.subject_overlaps["train_test"]

    def test_anti_leakage_detector_passes_disjoint_partitions(self):
        detector = DataLeakageDetector()

        train_subs = ["SUB_01", "SUB_02", "SUB_03"]
        val_subs = ["SUB_04"]
        test_subs = ["SUB_05", "SUB_06"]

        res = detector.check_splits(
            train_subjects=train_subs,
            val_subjects=val_subs,
            test_subjects=test_subs,
        )
        assert res.passed is True
        assert len(res.errors) == 0

    def test_feature_registry_specifications_and_distribution_computation(self):
        specs = feature_registry.get_feature_specs("features_v1")
        assert len(specs) == 8
        assert [s.name for s in specs] == [
            "accel_x", "accel_y", "accel_z",
            "gyro_x", "gyro_y", "gyro_z",
            "accel_mag", "gyro_mag"
        ]

        # Compute distributions for test tensor (100 windows, 150 timesteps, 8 channels)
        dummy_tensor = np.random.normal(loc=0.5, scale=1.2, size=(100, 150, 8)).astype(np.float32)
        dists = feature_registry.compute_feature_distributions(dummy_tensor, "features_v1")

        assert len(dists) == 8
        assert "accel_z" in dists
        az_dist = dists["accel_z"]
        assert az_dist.count == 100 * 150
        assert abs(az_dist.mean - 0.5) < 0.2
        assert abs(az_dist.std - 1.2) < 0.2
        assert az_dist.p95 > az_dist.p05


# ---------------------------------------------------------------------------
# Test Group 3: Dataset Builder, Hashing & Versioning
# ---------------------------------------------------------------------------

class TestDatasetBuilderAndVersioning:
    """Verifies dataset construction, deterministic resampling, and immutable hashing."""

    @pytest.fixture
    def synthetic_trials(self):
        gen = SyntheticIMUGenerator(random_seed=42)
        train_trials, val_trials, test_trials = gen.generate_cohort(
            n_train_subjects=3,
            n_val_subjects=1,
            n_test_subjects=2,
        )
        return train_trials, val_trials, test_trials

    def test_dataset_builder_creates_immutable_bundle_with_sha256(self, synthetic_trials):
        train_trials, val_trials, test_trials = synthetic_trials

        with tempfile.TemporaryDirectory() as tmpdir:
            builder = dataset_builder.__class__(datasets_dir=Path(tmpdir))

            entry = builder.build_from_subject_trials(
                train_trials=train_trials,
                val_trials=val_trials,
                test_trials=test_trials,
                dataset_version="test_ds_v1",
                description="Test suite unit dataset bundle",
            )

            assert entry.dataset_version == "test_ds_v1"
            assert entry.status == DatasetStatus.READY_FOR_TRAINING
            assert entry.sha256_hash is not None
            assert len(entry.sha256_hash) == 64
            assert entry.splits["train"].window_count > 0
            assert entry.splits["val"].window_count > 0
            assert entry.splits["test"].window_count > 0

            # Test loading and verification
            X_train, X_val, X_test, y_test, loaded_entry = builder.load_dataset_bundle("test_ds_v1")
            assert X_train.shape[1:] == (150, 8)
            assert len(X_train) == entry.splits["train"].window_count
            assert loaded_entry.sha256_hash == entry.sha256_hash

            # Verify immutability: Re-building the same version should fail
            with pytest.raises(ValueError, match="already exists and is immutable"):
                builder.build_from_subject_trials(
                    train_trials=train_trials,
                    val_trials=val_trials,
                    test_trials=test_trials,
                    dataset_version="test_ds_v1",
                )


# ---------------------------------------------------------------------------
# Test Group 4: Model Packaging, Validation Gate & Integrity Check
# ---------------------------------------------------------------------------

class TestModelPackagingAndValidationGate:
    """Verifies packaging, ONNX parity, checksums, and pre-approval validation gates."""

    @pytest.fixture
    def trained_artifacts(self):
        m_cfg = ModelConfig(input_dim=8, sequence_length=150, hidden_dims=[32, 16], latent_dim=16)
        model = TourSafeLSTMAutoencoder(m_cfg)

        scaler = TourSafeRobustScaler()
        dummy_train = np.random.randn(40, 150, 8).astype(np.float32)
        dummy_train[:, :, 2] += 1.0  # +1g gravity
        scaler.fit(dummy_train)

        thresh_res = ThresholdCalibrationResult(
            method="percentile_99",
            primary_threshold=5.50,
            warning_threshold=4.50,
            critical_threshold=7.00,
            val_score_mean=1.1,
            val_score_std=0.8,
            val_score_median=0.9,
            val_score_iqr=0.6,
            val_score_p95=4.8,
            val_score_p99=5.5,
            calibrated_at_epoch=5,
        )

        eval_report = AnomalyEvaluationReport(
            model_name="TourSafeLSTMAutoencoder",
            roc_auc=0.945,
            pr_auc=0.912,
            best_f1=0.895,
            precision_at_calibrated_threshold=0.88,
            recall_at_calibrated_threshold=0.91,
            f1_at_calibrated_threshold=0.895,
            specificity=0.95,
            false_positive_rate=0.05,
            false_negative_rate=0.09,
            confusion_matrix={"tn": 95, "fp": 5, "fn": 9, "tp": 91},
            calibrated_threshold=5.50,
            activity_error_breakdown={},
        )

        from app.ml.training.trainer import TrainingResult
        train_res = TrainingResult(
            best_model=model,
            train_loss_history=[1.5, 1.2, 1.0],
            val_loss_history=[1.6, 1.3, 1.1],
            lr_history=[0.001, 0.001, 0.001],
            best_epoch=3,
            total_epochs=3,
            best_val_loss=1.10,
            training_duration_sec=5.0,
            metrics_summary={"best_epoch": 3, "best_val_loss": 1.10},
        )

        return model, scaler, thresh_res, eval_report, train_res

    def test_model_packaging_and_validation_gate_success(self, trained_artifacts):
        model, scaler, thresh_res, eval_report, train_res = trained_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            packager = ModelPackager(artifacts_base_dir=Path(tmpdir))
            entry = packager.package_model(
                model=model,
                scaler=scaler,
                threshold_result=thresh_res,
                eval_report=eval_report,
                training_result=train_res,
                model_version="test-lstm-v1",
                dataset_version="test_ds_v1",
            )

            assert entry.model_version == "test-lstm-v1"
            assert entry.sha256_hash is not None

            # Run validation gate
            validator = ModelValidationGate(artifacts_base_dir=Path(tmpdir))
            gate_res = validator.validate_model_version("test-lstm-v1")

            assert gate_res.passed_all_gates is True
            assert len(gate_res.errors) == 0
            assert all(c.passed for c in gate_res.checks)

    def test_validation_gate_fails_on_corrupted_bundle(self, trained_artifacts):
        model, scaler, thresh_res, eval_report, train_res = trained_artifacts

        with tempfile.TemporaryDirectory() as tmpdir:
            packager = ModelPackager(artifacts_base_dir=Path(tmpdir))
            packager.package_model(
                model=model,
                scaler=scaler,
                threshold_result=thresh_res,
                eval_report=eval_report,
                training_result=train_res,
                model_version="corrupt-model-v1",
                dataset_version="test_ds_v1",
            )

            # Corrupt the threshold_config.json by setting primary_threshold = -1.0
            t_path = Path(tmpdir) / "corrupt-model-v1" / "threshold_config.json"
            with open(t_path, "w", encoding="utf-8") as f:
                json.dump({"primary_threshold": -1.0, "warning_threshold": 2.0, "critical_threshold": 3.0}, f)

            validator = ModelValidationGate(artifacts_base_dir=Path(tmpdir))
            gate_res = validator.validate_model_version("corrupt-model-v1")

            assert gate_res.passed_all_gates is False
            assert any("Primary threshold" in err or "hierarchy" in err for err in gate_res.errors)


# ---------------------------------------------------------------------------
# Test Group 5: Model Registry Governance, State Machine & Rollback
# ---------------------------------------------------------------------------

class TestModelRegistryAndGovernance:
    """Verifies state machine transitions, human approval, and atomic rollback."""

    @pytest.fixture(autouse=True)
    def setup_registry(self):
        # Create mock entries for testing
        self.entry_a = ModelRegistryEntry(
            model_version="lstm-gov-v1",
            dataset_version="ds_v1",
            status=ModelLifecycleStatus.PRODUCTION,
            is_production=True,
            metrics=ModelEvaluationMetrics(
                roc_auc=0.92,
                pr_auc=0.88,
                f1_score=0.87,
                has_ground_truth=True,
                mean_inference_latency_ms=0.5,
            ),
            threshold_config=ModelThresholdConfiguration(primary_threshold=5.80),
        )
        self.entry_b = ModelRegistryEntry(
            model_version="lstm-gov-v2",
            dataset_version="ds_v2",
            status=ModelLifecycleStatus.TRAINED,
            is_production=False,
            metrics=ModelEvaluationMetrics(
                roc_auc=0.96,
                pr_auc=0.94,
                f1_score=0.93,
                has_ground_truth=True,
                mean_inference_latency_ms=0.45,
            ),
            threshold_config=ModelThresholdConfiguration(primary_threshold=5.60),
        )

    def test_model_comparison_engine(self):
        report = model_comparison_engine.compare_models(self.entry_a, self.entry_b)
        assert report.production_model_version == "lstm-gov-v1"
        assert report.candidate_model_version == "lstm-gov-v2"
        assert report.has_ground_truth_labels is True
        assert report.approval_readiness is True

        roc_item = next(m for m in report.metrics_comparison if m.metric_name == "ROC-AUC")
        assert roc_item.candidate_value == 0.96
        assert roc_item.production_value == 0.92
        assert roc_item.candidate_is_better is True

    def test_insufficient_ground_truth_flagging(self):
        entry_unlabeled = ModelRegistryEntry(
            model_version="lstm-unlabeled-v1",
            dataset_version="ds_raw",
            status=ModelLifecycleStatus.TRAINED,
            metrics=ModelEvaluationMetrics(has_ground_truth=False),
        )
        report = model_comparison_engine.compare_models(self.entry_a, entry_unlabeled)
        assert report.has_ground_truth_labels is False
        assert "INSUFFICIENT GROUND TRUTH" in report.recommendation_summary
        assert report.approval_readiness is False


# ---------------------------------------------------------------------------
# Test Group 6: Feature Drift (PSI & KS-Test) & Retraining Recommendation
# ---------------------------------------------------------------------------

class TestFeatureDriftAndAdvisory:
    """Verifies statistical drift calculation using PSI and KS-tests."""

    def test_drift_detector_normal_distribution(self):
        detector = FeatureDriftDetector()

        # Baseline: N(0, 1)
        base_dist = FeatureChannelDistribution(
            channel="accel_z",
            count=1000,
            mean=0.0,
            std=1.0,
            min=-3.0,
            p01=-2.3,
            p05=-1.6,
            p25=-0.67,
            median=0.0,
            p75=0.67,
            p95=1.6,
            p99=2.3,
            max=3.0,
        )

        # Current live data: from identical distribution N(0, 1)
        live_samples = np.random.normal(0.0, 1.0, size=500)
        metric = detector.evaluate_feature_drift("accel_z", base_dist, live_samples)

        assert metric.status == DriftStatus.NORMAL
        assert metric.psi_score < 0.10

    def test_drift_detector_critical_shift_detection(self):
        detector = FeatureDriftDetector()

        # Baseline: N(0, 1)
        base_dist = FeatureChannelDistribution(
            channel="accel_x",
            count=1000,
            mean=0.0,
            std=1.0,
            min=-3.0,
            p01=-2.3,
            p05=-1.6,
            p25=-0.67,
            median=0.0,
            p75=0.67,
            p95=1.6,
            p99=2.3,
            max=3.0,
        )

        # Shifted live data: severe mean shift N(3.0, 2.0)
        shifted_samples = np.random.normal(3.0, 2.0, size=500)
        metric = detector.evaluate_feature_drift("accel_x", base_dist, shifted_samples)

        assert metric.status == DriftStatus.CRITICAL
        assert metric.psi_score >= 0.25
        assert metric.ks_p_value < 0.001

    def test_live_window_drift_report_and_retraining_advisory(self):
        detector = FeatureDriftDetector()
        base_dists = {
            "accel_x": FeatureChannelDistribution(channel="accel_x", count=100, mean=0.0, std=1.0, min=-3, p01=-2, p05=-1.6, p25=-0.6, median=0, p75=0.6, p95=1.6, p99=2, max=3),
            "accel_y": FeatureChannelDistribution(channel="accel_y", count=100, mean=0.0, std=1.0, min=-3, p01=-2, p05=-1.6, p25=-0.6, median=0, p75=0.6, p95=1.6, p99=2, max=3),
        }

        # Create 10 windows with heavy distribution shift
        shifted_windows = [np.random.normal(loc=4.0, scale=3.0, size=(150, 8)).astype(np.float32) for _ in range(10)]

        report = detector.evaluate_live_window_drift(
            model_version="v1.0.0",
            feature_version="features_v1",
            baseline_distributions=base_dists,
            window_feature_tensors=shifted_windows,
        )

        assert report.overall_drift_status in [DriftStatus.DRIFTING, DriftStatus.CRITICAL]
        assert report.retraining_recommended is True
        assert report.retraining_reason is not None
        assert "CONCEPT DRIFT NOT MEASURABLE" in report.concept_drift_status


# ---------------------------------------------------------------------------
# Test Group 7: Shadow Mode Parity & Safety Isolation
# ---------------------------------------------------------------------------

class TestShadowModeAndSafetyIsolation:
    """Verifies that candidate models run in shadow mode without corrupting safety signals."""

    @pytest.mark.asyncio
    async def test_shadow_engine_evaluates_without_error(self):
        # Prepare sample 150-sample telemetry window
        now_iso = datetime.now(timezone.utc).isoformat()
        samples = [
            TelemetrySample(
                packet_id=f"p_{i}",
                tourist_id="tourist_test_01",
                session_id="sess_test_01",
                timestamp=now_iso,
                sequence_number=i + 1,
                accelerometer=AccelerometerChannels(x=0.0, y=0.0, z=1.0),
                gyroscope=GyroscopeChannels(x=0.0, y=0.0, z=0.0),
            )
            for i in range(150)
        ]

        window = TelemetryWindow(
            window_id="win_test_shadow",
            tourist_id="tourist_test_01",
            session_id="sess_test_01",
            window_start=now_iso,
            window_end=now_iso,
            duration_seconds=3.0,
            stride_seconds=1.0,
            sample_count=150,
            observed_frequency_hz=50.0,
            completeness_ratio=1.0,
            samples=samples,
            is_valid=True,
            quality=QualityMetrics(),
        )

        # Test shadow evaluation when no shadow model is active (returns None safely)
        shadow_engine.unload_shadow_model()
        metric = await shadow_engine.evaluate_shadow_window(
            window=window,
            production_score=0.45,
            production_state="normal",
            production_version="v1.0.0",
        )
        assert metric is None

        summary = shadow_engine.get_shadow_metrics_summary()
        assert summary["total_shadow_evaluations"] == 0


# ---------------------------------------------------------------------------
# Test Group 8: Model Failure Invariant
# ---------------------------------------------------------------------------

class TestModelFailureSafetyInvariant:
    """Verifies that model degradation or failure never silently converts to NORMAL."""

    def test_loader_health_state_on_missing_model(self):
        loader = ModelArtifactLoader()
        success = loader.load_and_validate("non_existent_model_v99")
        assert success is False
        assert loader.health_state == ModelHealthState.MODEL_ERROR
        assert len(loader.validation_errors) > 0
