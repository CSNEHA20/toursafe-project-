"""
TourSafe Inference Preprocessor.
Faithfully recreates Prompt 8 preprocessing pipeline:
1. IMU feature extraction (6 raw + 2 derived magnitudes: accel_mag, gyro_mag)
2. Exact 50 Hz temporal grid resampling (150 timesteps for 3.0s window)
3. Robust IQR scaler transformation using loaded model artifacts.
"""

from datetime import datetime
import logging
from typing import Any, List, Optional, Tuple, Union
import numpy as np

from ...ml.preprocessing.feature_extractor import FeatureExtractor
from ...ml.preprocessing.resampler import IMUResampler
from ...schemas.telemetry import TelemetrySample, TelemetryWindow
from .loader import model_loader

logger = logging.getLogger("toursafe.ml.preprocessor")


class InferencePreprocessor:
    """
    Standardized inference preprocessor for real-time telemetry windows.
    """

    def __init__(self, target_length: int = 150, target_hz: float = 50.0):
        self.target_length = target_length
        self.target_hz = target_hz
        self.feature_extractor = FeatureExtractor(include_magnitudes=True)
        self.resampler = IMUResampler(target_hz=target_hz, max_gap_seconds=0.250)

    def preprocess_window(
        self,
        window: TelemetryWindow,
    ) -> Tuple[Optional[np.ndarray], Optional[str]]:
        """
        Transforms a TelemetryWindow into a normalized (1, 150, 8) tensor.
        Returns (preprocessed_array, None) on success or (None, rejection_reason) on failure.
        """
        if not window.is_valid:
            reason = "; ".join(window.validation_errors) if window.validation_errors else "Window marked invalid by telemetry engine"
            return None, f"Invalid window: {reason}"

        if not window.samples or len(window.samples) < 2:
            return None, f"Insufficient samples in window ({len(window.samples) if window.samples else 0} < 2)"

        if model_loader.scaler is None:
            return None, "ML Scaler artifact is not loaded"

        try:
            # 1. Extract timestamps in seconds relative to start of window
            sample_objs = window.samples
            timestamps_sec: List[float] = []
            raw_matrix: List[List[float]] = []

            for s in sample_objs:
                if isinstance(s, TelemetrySample):
                    dt = datetime.fromisoformat(s.timestamp.replace("Z", "+00:00"))
                    t_sec = dt.timestamp()
                    ax = float(s.accelerometer.x) if s.accelerometer else 0.0
                    ay = float(s.accelerometer.y) if s.accelerometer else 0.0
                    az = float(s.accelerometer.z) if s.accelerometer else 0.0
                    gx = float(s.gyroscope.x) if s.gyroscope else 0.0
                    gy = float(s.gyroscope.y) if s.gyroscope else 0.0
                    gz = float(s.gyroscope.z) if s.gyroscope else 0.0
                elif isinstance(s, dict):
                    t_val = s.get("timestamp", datetime.now().isoformat())
                    dt = datetime.fromisoformat(t_val.replace("Z", "+00:00"))
                    t_sec = dt.timestamp()
                    acc = s.get("accelerometer", {}) or {}
                    gyr = s.get("gyroscope", {}) or {}
                    ax = float(acc.get("x", s.get("accel_x", 0.0)))
                    ay = float(acc.get("y", s.get("accel_y", 0.0)))
                    az = float(acc.get("z", s.get("accel_z", 0.0)))
                    gx = float(gyr.get("x", s.get("gyro_x", 0.0)))
                    gy = float(gyr.get("y", s.get("gyro_y", 0.0)))
                    gz = float(gyr.get("z", s.get("gyro_z", 0.0)))
                else:
                    return None, f"Unsupported sample structure: {type(s)}"

                a_mag = float(np.sqrt(ax * ax + ay * ay + az * az))
                g_mag = float(np.sqrt(gx * gx + gy * gy + gz * gz))

                timestamps_sec.append(t_sec)
                raw_matrix.append([ax, ay, az, gx, gy, gz, a_mag, g_mag])

            ts_arr = np.array(timestamps_sec, dtype=np.float64)
            features_arr = np.array(raw_matrix, dtype=np.float32)

            # 2. Resample if length != target_length (e.g. 150)
            if len(features_arr) == self.target_length:
                resampled_feats = features_arr
            else:
                _, resampled_feats, is_resample_valid = self.resampler.resample_sequence(
                    timestamps_sec=ts_arr,
                    sensor_values=features_arr,
                    target_length=self.target_length,
                    duration_sec=window.duration_seconds or 3.0,
                )
                if not is_resample_valid:
                    return None, "Resampling detected excessive temporal gaps in IMU stream"

            # 3. Robust Scaling (transform)
            scaled = model_loader.scaler.transform(resampled_feats)

            # 4. Reshape to (1, 150, 8)
            tensor_input = np.expand_dims(scaled, axis=0).astype(np.float32)

            if tensor_input.shape != (1, self.target_length, 8):
                return None, f"Shape mismatch after preprocessing: expected (1, {self.target_length}, 8), got {tensor_input.shape}"

            return tensor_input, None

        except Exception as e:
            logger.warning(f"Error during window preprocessing: {e}")
            return None, f"Preprocessing exception: {str(e)}"


inference_preprocessor = InferencePreprocessor(target_length=150, target_hz=50.0)
