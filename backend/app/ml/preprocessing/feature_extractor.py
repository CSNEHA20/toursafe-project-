"""
TourSafe IMU Feature Extraction.
Extracts 6 raw IMU channels (accel x/y/z in g, gyro x/y/z in rad/s) and
computes derived vector magnitudes (accel_mag, gyro_mag) for canonical 8-channel input.
"""

from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np

from ..config import FEATURE_NAMES, RAW_IMU_CHANNELS


class FeatureExtractor:
    """
    Extracts, calculates, and structures kinematic features from raw telemetry dictionaries
    or TelemetrySample objects into standardized numpy matrices.
    """

    def __init__(self, include_magnitudes: bool = True):
        self.include_magnitudes = include_magnitudes
        self.feature_names = list(FEATURE_NAMES) if include_magnitudes else list(RAW_IMU_CHANNELS)

    @property
    def n_features(self) -> int:
        return len(self.feature_names)

    @staticmethod
    def compute_magnitudes(
        accel_x: np.ndarray,
        accel_y: np.ndarray,
        accel_z: np.ndarray,
        gyro_x: np.ndarray,
        gyro_y: np.ndarray,
        gyro_z: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes L2 vector magnitudes for acceleration and angular velocity.
        accel_mag = sqrt(ax^2 + ay^2 + az^2)
        gyro_mag = sqrt(gx^2 + gy^2 + gz^2)
        """
        accel_mag = np.sqrt(np.square(accel_x) + np.square(accel_y) + np.square(accel_z))
        gyro_mag = np.sqrt(np.square(gyro_x) + np.square(gyro_y) + np.square(gyro_z))
        return accel_mag, gyro_mag

    def extract_from_raw_array(self, raw_6ch: np.ndarray) -> np.ndarray:
        """
        Converts (..., 6) raw IMU array [ax, ay, az, gx, gy, gz] into (..., 8) feature array.
        """
        raw_6ch = np.asarray(raw_6ch, dtype=np.float32)
        if raw_6ch.shape[-1] != 6:
            raise ValueError(f"Expected last dimension 6 for raw IMU channels, got {raw_6ch.shape[-1]}")

        if not self.include_magnitudes:
            return raw_6ch

        ax = raw_6ch[..., 0]
        ay = raw_6ch[..., 1]
        az = raw_6ch[..., 2]
        gx = raw_6ch[..., 3]
        gy = raw_6ch[..., 4]
        gz = raw_6ch[..., 5]

        a_mag, g_mag = self.compute_magnitudes(ax, ay, az, gx, gy, gz)
        a_mag = np.expand_dims(a_mag, axis=-1)
        g_mag = np.expand_dims(g_mag, axis=-1)

        return np.concatenate([raw_6ch, a_mag, g_mag], axis=-1)

    def extract_from_sample_dict(self, sample: Dict[str, Any]) -> np.ndarray:
        """
        Extracts 8-channel vector from a telemetry sample dictionary.
        Handles both flattened and nested formats (e.g. sample["accelerometer"]["x"]).
        """
        if "accelerometer" in sample and isinstance(sample["accelerometer"], dict):
            ax = float(sample["accelerometer"]["x"])
            ay = float(sample["accelerometer"]["y"])
            az = float(sample["accelerometer"]["z"])
        else:
            ax = float(sample.get("accel_x", sample.get("ax", 0.0)))
            ay = float(sample.get("accel_y", sample.get("ay", 0.0)))
            az = float(sample.get("accel_z", sample.get("az", 0.0)))

        if "gyroscope" in sample and isinstance(sample["gyroscope"], dict):
            gx = float(sample["gyroscope"]["x"])
            gy = float(sample["gyroscope"]["y"])
            gz = float(sample["gyroscope"]["z"])
        else:
            gx = float(sample.get("gyro_x", sample.get("gx", 0.0)))
            gy = float(sample.get("gyro_y", sample.get("gy", 0.0)))
            gz = float(sample.get("gyro_z", sample.get("gz", 0.0)))

        raw_vector = np.array([ax, ay, az, gx, gy, gz], dtype=np.float32)
        if not self.include_magnitudes:
            return raw_vector

        a_mag = float(np.sqrt(ax * ax + ay * ay + az * az))
        g_mag = float(np.sqrt(gx * gx + gy * gy + gz * gz))
        return np.array([ax, ay, az, gx, gy, gz, a_mag, g_mag], dtype=np.float32)

    def extract_from_window_samples(self, samples: Sequence[Any]) -> np.ndarray:
        """
        Converts a sequence of sample dicts or Pydantic models into a (T, n_features) array.
        """
        rows = []
        for s in samples:
            if hasattr(s, "model_dump"):
                d = s.model_dump()
            elif hasattr(s, "dict"):
                d = s.dict()
            elif isinstance(s, dict):
                d = s
            else:
                raise TypeError(f"Unsupported sample type: {type(s)}")
            rows.append(self.extract_from_sample_dict(d))

        return np.stack(rows, axis=0) if rows else np.zeros((0, self.n_features), dtype=np.float32)


default_feature_extractor = FeatureExtractor(include_magnitudes=True)
