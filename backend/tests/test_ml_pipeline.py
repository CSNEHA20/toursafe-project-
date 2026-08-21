"""
Unit and Integration Tests for TourSafe ML Data & Training Pipeline.
Verifies resampling, feature extraction, robust scaling, anti-leakage splitting,
LSTM Autoencoder architecture, threshold calibration, and ONNX parity.
"""

import json
import tempfile
from pathlib import Path
import numpy as np
import pytest
import torch

from app.ml.config import ModelConfig, PipelineConfig, WindowConfig
from app.ml.dataset.dataset_builder import DatasetBuilder, DatasetBundle
from app.ml.dataset.synthetic_generator import SyntheticIMUGenerator
from app.ml.evaluation.evaluator import ModelEvaluator
from app.ml.evaluation.threshold import AnomalyThresholdCalibrator, ThresholdCalibrationResult
from app.ml.models.baselines import IsolationForestDetector, KinematicPeakDetector
from app.ml.models.lstm_autoencoder import TourSafeLSTMAutoencoder
from app.ml.preprocessing.feature_extractor import FeatureExtractor
from app.ml.preprocessing.resampler import IMUResampler
from app.ml.preprocessing.scaler import TourSafeRobustScaler
from app.ml.artifacts.manager import ModelArtifactManager
from app.ml.training.trainer import AutoencoderTrainer


class TestIMUResampler:
    def test_resample_uniform_grid(self):
        resampler = IMUResampler(target_hz=50.0)
        # Create 3 seconds of jittered data (~150 samples)
        t_jittered = np.sort(np.random.uniform(0.0, 3.0, size=140))
        t_jittered[0] = 0.0
        t_jittered[-1] = 3.0
        values = np.sin(2 * np.pi * 1.5 * t_jittered)[:, np.newaxis]

        t_out, v_out, is_valid = resampler.resample_sequence(
            timestamps_sec=t_jittered,
            sensor_values=values,
            target_length=150,
            duration_sec=3.0,
        )

        assert is_valid is True
        assert len(t_out) == 150
        assert v_out.shape == (150, 1)
        # Timesteps should be exactly uniform
        dt = np.diff(t_out)
        np.testing.assert_allclose(dt, dt[0], atol=1e-5)

    def test_detects_excessive_time_gap(self):
        resampler = IMUResampler(target_hz=50.0, max_gap_seconds=0.250)
        # Create timestamps with a 500ms gap
        t = np.array([0.0, 0.5, 0.52, 0.54, 1.1, 1.12, 3.0])  # gap between 0.54 and 1.1 is 560ms
        vals = np.ones((len(t), 3))

        _, _, is_valid = resampler.resample_sequence(t, vals, target_length=150, duration_sec=3.0)
        assert is_valid is False


class TestFeatureExtractor:
    def test_computes_magnitudes_correctly(self):
        extractor = FeatureExtractor(include_magnitudes=True)
        assert extractor.n_features == 8

        # Dummy raw IMU (10 samples, 6 channels: ax=3, ay=4, az=0, gx=0, gy=6, gz=8)
        raw = np.zeros((10, 6), dtype=np.float32)
        raw[:, 0] = 3.0
        raw[:, 1] = 4.0
        raw[:, 4] = 6.0
        raw[:, 5] = 8.0

        feat_8ch = extractor.extract_from_raw_array(raw)
        assert feat_8ch.shape == (10, 8)
        # Accel mag = sqrt(3^2 + 4^2) = 5.0
        np.testing.assert_allclose(feat_8ch[:, 6], 5.0, atol=1e-5)
        # Gyro mag = sqrt(6^2 + 8^2) = 10.0
        np.testing.assert_allclose(feat_8ch[:, 7], 10.0, atol=1e-5)


class TestTourSafeRobustScaler:
    def test_fit_transform_and_serialization(self):
        scaler = TourSafeRobustScaler()
        # Normal data with few extreme outliers
        X = np.random.normal(0, 1, size=(50, 150, 8)).astype(np.float32)
        X[0, 10, :] = 500.0  # extreme outlier

        scaled = scaler.fit_transform(X)
        assert scaled.shape == (50, 150, 8)
        assert scaler.is_fitted is True

        # Test dictionary export/import
        d = scaler.to_dict()
        scaler_reloaded = TourSafeRobustScaler.from_dict(d)
        np.testing.assert_allclose(scaler.center_, scaler_reloaded.center_)
        np.testing.assert_allclose(scaler.scale_, scaler_reloaded.scale_)

        # Test inverse transform
        recovered = scaler.inverse_transform(scaled)
        np.testing.assert_allclose(recovered, X, atol=1e-4)


class TestDatasetBuilderAndAntiLeakage:
    def test_anti_leakage_and_splitting(self):
        gen = SyntheticIMUGenerator(target_hz=50.0, random_seed=123)
        tr_trials, val_trials, te_trials = gen.generate_cohort(
            n_train_subjects=4,
            n_val_subjects=2,
            n_test_subjects=2,
        )

        builder = DatasetBuilder()
        bundle: DatasetBundle = builder.build_dataset_bundle(tr_trials, val_trials, te_trials)

        # 1. Check window tensor shapes
        assert bundle.X_train_normal.ndim == 3
        assert bundle.X_train_normal.shape[1:] == (150, 8)
        assert bundle.X_val_normal.shape[1:] == (150, 8)
        assert bundle.X_test.shape[1:] == (150, 8)

        # 2. Check subject anti-leakage guarantee
        tr_subs = set(bundle.train_subjects)
        val_subs = set(bundle.val_subjects)
        te_subs = set(bundle.test_subjects)

        assert len(tr_subs.intersection(val_subs)) == 0
        assert len(tr_subs.intersection(te_subs)) == 0
        assert len(val_subs.intersection(te_subs)) == 0

        # 3. Check labels: Train and Val have NO anomaly windows; Test has both
        assert len(bundle.X_train_normal) > 0
        assert len(bundle.X_val_normal) > 0
        assert np.sum(bundle.y_test == 0) > 0  # normal test windows
        assert np.sum(bundle.y_test == 1) > 0  # anomaly test windows


class TestLSTMAutoencoder:
    def test_forward_pass_and_reconstruction(self):
        cfg = ModelConfig(input_dim=8, sequence_length=150, hidden_dims=[32, 16], latent_dim=8)
        model = TourSafeLSTMAutoencoder(cfg)

        batch = torch.randn(4, 150, 8)
        recon = model(batch)
        assert recon.shape == (4, 150, 8)

        latent = model.encode(batch)
        assert latent.shape == (4, 8)

        mse_scores = model.compute_reconstruction_error(batch, error_type="mse")
        assert mse_scores.shape == (4,)
        assert torch.all(mse_scores >= 0)

        timestep_errs = model.compute_per_timestep_error(batch)
        assert timestep_errs.shape == (4, 150)


class TestThresholdCalibrator:
    def test_calibration_rules(self):
        calibrator = AnomalyThresholdCalibrator()
        # Normal distribution of validation errors
        val_errors = np.random.gamma(shape=2.0, scale=0.01, size=200)

        res = calibrator.calibrate(val_errors, method="percentile_99")
        assert res.primary_threshold > res.val_score_mean
        assert res.warning_threshold <= res.primary_threshold
        assert res.critical_threshold >= res.primary_threshold

        res_dict = res.to_dict()
        assert "primary_threshold" in res_dict
        assert "val_score_median" in res_dict


class TestONNXParityAndArtifactManager:
    def test_onnx_export_and_loading(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cfg = ModelConfig(input_dim=8, sequence_length=150, hidden_dims=[32, 16], latent_dim=8)
            model = TourSafeLSTMAutoencoder(cfg)
            scaler = TourSafeRobustScaler()
            X_dummy = np.random.randn(20, 150, 8).astype(np.float32)
            scaler.fit(X_dummy)

            val_errs = np.array([0.01, 0.012, 0.009, 0.011, 0.015, 0.013])
            calibrator = AnomalyThresholdCalibrator()
            th_res = calibrator.calibrate(val_errs)

            from app.ml.config import ArtifactConfig
            art_cfg = ArtifactConfig(version="v_test", base_dir=tmp_path / "artifacts", experiments_dir=tmp_path / "experiments")
            manager = ModelArtifactManager(art_cfg)

            # Save bundle
            meta = manager.save_artifact_bundle(
                model=model,
                scaler=scaler,
                threshold_result=th_res,
                version="v_test",
            )

            assert meta["onnx_export"]["parity_verified"] is True
            assert meta["onnx_export"]["max_absolute_difference"] < 1e-4

            # Verify files exist
            ver_dir = tmp_path / "artifacts" / "v_test"
            assert (ver_dir / "model.pt").exists()
            assert (ver_dir / "model.onnx").exists()
            assert (ver_dir / "scaler.joblib").exists()
            assert (ver_dir / "scaler_config.json").exists()
            assert (ver_dir / "threshold_config.json").exists()
            assert (ver_dir / "metadata.json").exists()

            # Load bundle
            loaded_model, loaded_scaler, loaded_th, loaded_meta = manager.load_artifact_bundle(version="v_test")
            assert loaded_scaler.is_fitted is True
            assert loaded_th.primary_threshold == th_res.primary_threshold
            assert loaded_model.config.sequence_length == 150
