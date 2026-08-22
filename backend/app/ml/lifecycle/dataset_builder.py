"""
TourSafe Dataset Construction Pipeline.
Builds immutable, versioned datasets from canonical MongoDB telemetry samples
or benchmark subject trials with deterministic resampling, quality filtering,
anti-leakage guarantees, and comprehensive quality reports.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from ...core.config import settings
from ...core import database as db_core
from ...schemas.ml_lifecycle import (
    DataQualitySummary,
    DatasetBuildRequest,
    DatasetRegistryEntry,
    DatasetSplitSummary,
    DatasetStatus,
)
from ..config import WindowConfig
from ..preprocessing.feature_extractor import default_feature_extractor
from ..preprocessing.resampler import IMUResampler
from .data_quality import data_quality_reporter
from .data_validator import ValidationResult, raw_telemetry_validator
from .feature_registry import feature_registry
from .leakage_detector import leakage_detector

logger = logging.getLogger("toursafe.ml.dataset_builder")


class DatasetBuilder:
    """
    Constructs versioned datasets conforming to TourSafe ML standards.
    """

    def __init__(
        self,
        datasets_dir: Optional[Path] = None,
        window_config: Optional[WindowConfig] = None,
    ):
        base = Path(__file__).resolve().parent.parent / "datasets"
        self.datasets_dir = datasets_dir or base
        self.datasets_dir.mkdir(parents=True, exist_ok=True)
        self.window_config = window_config or WindowConfig()
        self.resampler = IMUResampler(
            target_hz=self.window_config.nominal_frequency_hz,
            max_gap_seconds=self.window_config.max_time_gap_ms / 1000.0,
        )

    def extract_windows_from_session_samples(
        self,
        samples: List[Dict[str, Any]],
        subject_id: str,
        session_id: str,
        is_anomaly: bool = False,
        stride_seconds: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Slices validated session samples into 3-second windows with deterministic resampling.
        """
        if not samples:
            return []

        stride_sec = stride_seconds if stride_seconds is not None else self.window_config.stride_seconds
        dur_sec = self.window_config.duration_seconds
        target_len = self.window_config.window_samples

        # Extract timestamps, accel, gyro
        ts_list = []
        raw_6ch_list = []
        for s in samples:
            raw_ts = s.get("timestamp")
            if isinstance(raw_ts, (int, float)):
                t_sec = float(raw_ts) / 1000.0 if raw_ts > 1e11 else float(raw_ts)
            elif isinstance(raw_ts, datetime):
                t_sec = raw_ts.timestamp()
            elif isinstance(raw_ts, str):
                t_sec = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).timestamp()
            else:
                continue

            acc = s.get("accelerometer", {})
            gyr = s.get("gyroscope", {})
            ax, ay, az = acc.get("x", 0.0), acc.get("y", 0.0), acc.get("z", 1.0)
            gx, gy, gz = gyr.get("x", 0.0), gyr.get("y", 0.0), gyr.get("z", 0.0)

            ts_list.append(t_sec)
            raw_6ch_list.append([ax, ay, az, gx, gy, gz])

        if len(ts_list) < int(round(target_len * 0.6)):
            return []

        ts = np.asarray(ts_list, dtype=np.float64)
        raw_6ch = np.asarray(raw_6ch_list, dtype=np.float32)

        total_span = ts[-1] - ts[0]
        if total_span < dur_sec:
            return []

        windows: List[Dict[str, Any]] = []
        anchor_t = ts[0]
        while (anchor_t + dur_sec) <= ts[-1]:
            window_end_t = anchor_t + dur_sec
            mask = (ts >= anchor_t) & (ts <= window_end_t)
            w_ts = ts[mask]
            w_raw = raw_6ch[mask]

            if len(w_ts) >= int(round(target_len * self.window_config.min_completeness_ratio)):
                rel_ts = w_ts - w_ts[0]
                _, resampled_6ch, is_valid = self.resampler.resample_sequence(
                    timestamps_sec=rel_ts,
                    sensor_values=w_raw,
                    target_length=target_len,
                    duration_sec=dur_sec,
                )
                if is_valid:
                    feat_8ch = default_feature_extractor.extract_from_raw_array(resampled_6ch)
                    windows.append({
                        "features": feat_8ch,  # (150, 8)
                        "subject_id": subject_id,
                        "session_id": session_id,
                        "is_anomaly": is_anomaly,
                    })

            anchor_t += stride_sec

        return windows

    def build_from_subject_trials(
        self,
        train_trials: List[Dict[str, Any]],
        val_trials: List[Dict[str, Any]],
        test_trials: List[Dict[str, Any]],
        dataset_version: str,
        description: str = "Subject-partitioned IMU benchmark dataset",
        feature_version: str = "features_v1",
    ) -> DatasetRegistryEntry:
        """
        Constructs, validates, hashes, and persists a dataset bundle from structured subject trials.
        """
        target_dir = self.datasets_dir / dataset_version
        if target_dir.exists():
            raise ValueError(f"Dataset version '{dataset_version}' already exists and is immutable!")

        target_dir.mkdir(parents=True, exist_ok=True)

        validation_results: List[ValidationResult] = []

        # Validate trials
        for trial in train_trials + val_trials + test_trials:
            samples = []
            ts = trial["timestamps_sec"]
            acc = trial["accel"]
            gyr = trial["gyro"]
            for i in range(len(ts)):
                samples.append({
                    "timestamp": ts[i],
                    "session_id": trial.get("session_id", trial["subject_id"]),
                    "accelerometer": {"x": float(acc[i, 0]), "y": float(acc[i, 1]), "z": float(acc[i, 2])},
                    "gyroscope": {"x": float(gyr[i, 0]), "y": float(gyr[i, 1]), "z": float(gyr[i, 2])},
                })
            v_res = raw_telemetry_validator.validate_session_stream(samples, session_id=trial.get("session_id"))
            validation_results.append(v_res)

        # 1. Process Train Windows (Normal only)
        X_train_list, train_subs, train_sess = [], [], []
        for trial in train_trials:
            if trial.get("is_anomaly", False):
                continue
            samples = []
            for i in range(len(trial["timestamps_sec"])):
                samples.append({
                    "timestamp": trial["timestamps_sec"][i],
                    "accelerometer": {"x": float(trial["accel"][i, 0]), "y": float(trial["accel"][i, 1]), "z": float(trial["accel"][i, 2])},
                    "gyroscope": {"x": float(trial["gyro"][i, 0]), "y": float(trial["gyro"][i, 1]), "z": float(trial["gyro"][i, 2])},
                })
            sub_id = trial["subject_id"]
            sess_id = trial.get("session_id", f"sess_{sub_id}")
            w_list = self.extract_windows_from_session_samples(samples, sub_id, sess_id, is_anomaly=False, stride_seconds=1.0)
            for w in w_list:
                X_train_list.append(w["features"])
                train_subs.append(w["subject_id"])
                train_sess.append(w["session_id"])

        # 2. Process Validation Windows (Normal only)
        X_val_list, val_subs, val_sess = [], [], []
        for trial in val_trials:
            if trial.get("is_anomaly", False):
                continue
            samples = []
            for i in range(len(trial["timestamps_sec"])):
                samples.append({
                    "timestamp": trial["timestamps_sec"][i],
                    "accelerometer": {"x": float(trial["accel"][i, 0]), "y": float(trial["accel"][i, 1]), "z": float(trial["accel"][i, 2])},
                    "gyroscope": {"x": float(trial["gyro"][i, 0]), "y": float(trial["gyro"][i, 1]), "z": float(trial["gyro"][i, 2])},
                })
            sub_id = trial["subject_id"]
            sess_id = trial.get("session_id", f"sess_{sub_id}")
            w_list = self.extract_windows_from_session_samples(samples, sub_id, sess_id, is_anomaly=False, stride_seconds=1.5)
            for w in w_list:
                X_val_list.append(w["features"])
                val_subs.append(w["subject_id"])
                val_sess.append(w["session_id"])

        # 3. Process Test Windows (Normal + Anomalies)
        X_test_list, y_test_list, test_subs, test_sess = [], [], [], []
        for trial in test_trials:
            is_anom = bool(trial.get("is_anomaly", False))
            samples = []
            for i in range(len(trial["timestamps_sec"])):
                samples.append({
                    "timestamp": trial["timestamps_sec"][i],
                    "accelerometer": {"x": float(trial["accel"][i, 0]), "y": float(trial["accel"][i, 1]), "z": float(trial["accel"][i, 2])},
                    "gyroscope": {"x": float(trial["gyro"][i, 0]), "y": float(trial["gyro"][i, 1]), "z": float(trial["gyro"][i, 2])},
                })
            sub_id = trial["subject_id"]
            sess_id = trial.get("session_id", f"sess_{sub_id}")
            w_list = self.extract_windows_from_session_samples(samples, sub_id, sess_id, is_anomaly=is_anom, stride_seconds=1.0)
            for w in w_list:
                X_test_list.append(w["features"])
                y_test_list.append(1 if is_anom else 0)
                test_subs.append(w["subject_id"])
                test_sess.append(w["session_id"])

        X_train = np.array(X_train_list, dtype=np.float32)
        X_val = np.array(X_val_list, dtype=np.float32)
        X_test = np.array(X_test_list, dtype=np.float32)
        y_test = np.array(y_test_list, dtype=np.int64)

        # 4. Anti-Leakage Verification
        leak_res = leakage_detector.check_splits(
            train_subjects=train_subs,
            val_subjects=val_subs,
            test_subjects=test_subs,
            train_sessions=train_sess,
            val_sessions=val_sess,
            test_sessions=test_sess,
            X_train=X_train,
            X_test=X_test,
        )
        if not leak_res.passed:
            raise ValueError(f"Data leakage detected during dataset build: {leak_res.errors}")

        # 5. Quality Report
        total_sessions = len(set(train_sess + val_sess + test_sess))
        total_subjects = len(set(train_subs + val_subs + test_subs))
        quality_summary = data_quality_reporter.compile_summary(
            validation_results,
            total_sessions=total_sessions,
            total_subjects=total_subjects,
        )

        # 6. Feature Distributions
        feature_dists = feature_registry.compute_feature_distributions(
            X_train,
            feature_version=feature_version,
        )

        # 7. Persist .npz tensor bundle
        bundle_path = target_dir / "dataset_bundle.npz"
        np.savez_compressed(
            bundle_path,
            X_train=X_train,
            X_val=X_val,
            X_test=X_test,
            y_test=y_test,
        )

        # Compute SHA-256 hash of dataset bundle
        sha256 = hashlib.sha256()
        with open(bundle_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        digest = sha256.hexdigest()

        splits = {
            "train": DatasetSplitSummary(
                split_name="train",
                window_count=len(X_train),
                subject_count=len(set(train_subs)),
                subject_ids=sorted(list(set(train_subs))),
                session_count=len(set(train_sess)),
                session_ids=sorted(list(set(train_sess))),
                normal_windows=len(X_train),
                anomaly_windows=0,
            ),
            "val": DatasetSplitSummary(
                split_name="val",
                window_count=len(X_val),
                subject_count=len(set(val_subs)),
                subject_ids=sorted(list(set(val_subs))),
                session_count=len(set(val_sess)),
                session_ids=sorted(list(set(val_sess))),
                normal_windows=len(X_val),
                anomaly_windows=0,
            ),
            "test": DatasetSplitSummary(
                split_name="test",
                window_count=len(X_test),
                subject_count=len(set(test_subs)),
                subject_ids=sorted(list(set(test_subs))),
                session_count=len(set(test_sess)),
                session_ids=sorted(list(set(test_sess))),
                normal_windows=int(np.sum(y_test == 0)),
                anomaly_windows=int(np.sum(y_test == 1)),
            ),
        }

        entry = DatasetRegistryEntry(
            dataset_version=dataset_version,
            description=description,
            feature_version=feature_version,
            status=DatasetStatus.READY_FOR_TRAINING,
            created_at=datetime.now(timezone.utc).isoformat(),
            total_raw_records=quality_summary.total_samples_inspected,
            total_windows=len(X_train) + len(X_val) + len(X_test),
            splits=splits,
            quality_report=quality_summary,
            feature_distributions=feature_dists,
            artifact_path=str(bundle_path),
            sha256_hash=digest,
        )

        manifest_path = target_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(entry.model_dump(), f, indent=2)

        return entry

    def load_dataset_bundle(self, dataset_version: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, DatasetRegistryEntry]:
        """
        Loads the partitioned numpy arrays and verified metadata for a dataset version.
        """
        target_dir = self.datasets_dir / dataset_version
        bundle_path = target_dir / "dataset_bundle.npz"
        manifest_path = target_dir / "manifest.json"

        if not bundle_path.exists() or not manifest_path.exists():
            raise FileNotFoundError(f"Dataset '{dataset_version}' bundle or manifest not found in {target_dir}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            entry = DatasetRegistryEntry.model_validate(json.load(f))

        # Verify hash integrity
        sha256 = hashlib.sha256()
        with open(bundle_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        if entry.sha256_hash and sha256.hexdigest() != entry.sha256_hash:
            raise ValueError(f"Dataset '{dataset_version}' integrity verification failed (SHA-256 mismatch)")

        data = np.load(bundle_path)
        X_train = data["X_train"]
        X_val = data["X_val"]
        X_test = data["X_test"]
        y_test = data["y_test"]

        return X_train, X_val, X_test, y_test, entry


dataset_builder = DatasetBuilder()
