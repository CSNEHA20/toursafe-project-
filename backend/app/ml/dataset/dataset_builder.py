"""
TourSafe IMU Dataset Builder.
Generates temporal windows, performs subject-wise splitting, and validates
anti-leakage guarantees for normal-motion training and anomalous evaluation.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from ..config import WindowConfig
from ..preprocessing.feature_extractor import FeatureExtractor, default_feature_extractor
from ..preprocessing.resampler import IMUResampler


@dataclass
class DatasetBundle:
    """Container holding partitioned train, validation, and test datasets."""
    X_train_normal: np.ndarray       # Shape (N_train, 150, 8) - Normal sequences only
    train_subjects: List[str]        # Subject ID per train window
    X_val_normal: np.ndarray         # Shape (N_val, 150, 8) - Normal validation
    val_subjects: List[str]          # Subject ID per val window
    X_test: np.ndarray               # Shape (N_test, 150, 8) - Normal + Abnormal benchmark
    y_test: np.ndarray               # Shape (N_test,) - Binary labels (0: Normal, 1: Anomaly)
    test_activities: List[str]       # Activity name per test window
    test_subjects: List[str]         # Subject ID per test window
    feature_names: List[str]         # Channel names
    summary: Dict[str, Any]          # Dataset summary metrics


class DatasetBuilder:
    """
    Constructs normalized 3-second temporal windows from continuous IMU trials.
    Guarantees strict subject-wise partitioning to prevent data leakage.
    """

    def __init__(
        self,
        window_config: Optional[WindowConfig] = None,
        feature_extractor: Optional[FeatureExtractor] = None,
    ):
        self.window_config = window_config or WindowConfig()
        self.feature_extractor = feature_extractor or default_feature_extractor
        self.resampler = IMUResampler(
            target_hz=self.window_config.nominal_frequency_hz,
            max_gap_seconds=self.window_config.max_time_gap_ms / 1000.0,
        )

    def extract_windows_from_trial(
        self,
        trial: Dict[str, Any],
        stride_seconds: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Slices a continuous trial into sliding temporal windows, resamples to 50 Hz,
        and derives 8 feature channels.
        """
        ts = np.asarray(trial["timestamps_sec"], dtype=np.float64)
        accel = np.asarray(trial["accel"], dtype=np.float32)
        gyro = np.asarray(trial["gyro"], dtype=np.float32)
        sub_id = trial["subject_id"]
        act = trial["activity"]
        is_anom = bool(trial.get("is_anomaly", False))

        duration_sec = self.window_config.duration_seconds
        stride_sec = stride_seconds if stride_seconds is not None else self.window_config.stride_seconds
        target_len = self.window_config.window_samples

        total_span = ts[-1] - ts[0] if len(ts) > 1 else 0.0
        if total_span < duration_sec:
            return []

        raw_6ch = np.concatenate([accel, gyro], axis=1)  # (N, 6)
        windows: List[Dict[str, Any]] = []

        anchor_t = ts[0]
        while (anchor_t + duration_sec) <= ts[-1]:
            window_end_t = anchor_t + duration_sec

            # Mask samples in [anchor_t, window_end_t]
            mask = (ts >= anchor_t) & (ts <= window_end_t)
            w_ts = ts[mask]
            w_raw = raw_6ch[mask]

            if len(w_ts) >= int(round(target_len * self.window_config.min_completeness_ratio)):
                # Resample to exact 150 samples @ 50 Hz
                rel_ts = w_ts - w_ts[0]
                _, resampled_6ch, is_valid = self.resampler.resample_sequence(
                    timestamps_sec=rel_ts,
                    sensor_values=w_raw,
                    target_length=target_len,
                    duration_sec=duration_sec,
                )

                if is_valid:
                    # Extract 8 features (6 raw + 2 vector magnitudes)
                    feat_8ch = self.feature_extractor.extract_from_raw_array(resampled_6ch)

                    windows.append({
                        "features": feat_8ch,  # (150, 8)
                        "subject_id": sub_id,
                        "activity": act,
                        "is_anomaly": is_anom,
                    })

            anchor_t += stride_sec

        return windows

    def build_dataset_bundle(
        self,
        train_trials: List[Dict[str, Any]],
        val_trials: List[Dict[str, Any]],
        test_trials: List[Dict[str, Any]],
    ) -> DatasetBundle:
        """
        Transforms raw multi-subject trial lists into a verified DatasetBundle.
        Asserts zero subject overlap across splits.
        """
        train_subs: Set[str] = {t["subject_id"] for t in train_trials}
        val_subs: Set[str] = {t["subject_id"] for t in val_trials}
        test_subs: Set[str] = {t["subject_id"] for t in test_trials}

        # Verify anti-leakage invariant
        overlap_tr_val = train_subs.intersection(val_subs)
        overlap_tr_te = train_subs.intersection(test_subs)
        overlap_val_te = val_subs.intersection(test_subs)

        if overlap_tr_val or overlap_tr_te or overlap_val_te:
            raise ValueError(
                f"Data leakage detected! Subject overlap found: "
                f"Train/Val={overlap_tr_val}, Train/Test={overlap_tr_te}, Val/Test={overlap_val_te}"
            )

        # 1. Process Train Windows (Normal only, 1.0s stride)
        X_train_list = []
        train_sub_list = []
        for trial in train_trials:
            if trial.get("is_anomaly", False):
                continue  # Train set must only contain normal movement
            w_list = self.extract_windows_from_trial(trial, stride_seconds=1.0)
            for w in w_list:
                X_train_list.append(w["features"])
                train_sub_list.append(w["subject_id"])

        # 2. Process Validation Windows (Normal only, 1.5s stride)
        X_val_list = []
        val_sub_list = []
        for trial in val_trials:
            if trial.get("is_anomaly", False):
                continue  # Validation set for early stopping must be normal
            w_list = self.extract_windows_from_trial(trial, stride_seconds=1.5)
            for w in w_list:
                X_val_list.append(w["features"])
                val_sub_list.append(w["subject_id"])

        # 3. Process Test Windows (Normal + Abnormal benchmark, 1.5s stride)
        X_test_list = []
        y_test_list = []
        test_act_list = []
        test_sub_list = []
        for trial in test_trials:
            w_list = self.extract_windows_from_trial(trial, stride_seconds=1.5)
            for w in w_list:
                X_test_list.append(w["features"])
                y_test_list.append(1 if w["is_anomaly"] else 0)
                test_act_list.append(w["activity"])
                test_sub_list.append(w["subject_id"])

        X_train = np.array(X_train_list, dtype=np.float32)
        X_val = np.array(X_val_list, dtype=np.float32)
        X_test = np.array(X_test_list, dtype=np.float32)
        y_test = np.array(y_test_list, dtype=np.int64)

        summary = {
            "n_train_windows": len(X_train),
            "n_train_subjects": len(train_subs),
            "n_val_windows": len(X_val),
            "n_val_subjects": len(val_subs),
            "n_test_windows": len(X_test),
            "n_test_normal_windows": int(np.sum(y_test == 0)),
            "n_test_anomaly_windows": int(np.sum(y_test == 1)),
            "n_test_subjects": len(test_subs),
            "window_shape": list(X_train.shape[1:]) if len(X_train) > 0 else [150, 8],
            "train_subject_ids": sorted(list(train_subs)),
            "val_subject_ids": sorted(list(val_subs)),
            "test_subject_ids": sorted(list(test_subs)),
        }

        return DatasetBundle(
            X_train_normal=X_train,
            train_subjects=train_sub_list,
            X_val_normal=X_val,
            val_subjects=val_sub_list,
            X_test=X_test,
            y_test=y_test,
            test_activities=test_act_list,
            test_subjects=test_sub_list,
            feature_names=self.feature_extractor.feature_names,
            summary=summary,
        )
