"""
TourSafe Feature Registry & Specification.
Defines canonical sensor channels, physical units, dynamic valid bounds,
feature versioning (e.g. features_v1), transformations, and distribution summaries.
"""

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Dict, List, Optional
import numpy as np

from ...schemas.ml_lifecycle import FeatureChannelDistribution


@dataclass
class FeatureSpec:
    name: str
    physical_unit: str
    source_channel: str
    transformation: str
    min_physical_bound: float
    max_physical_bound: float
    description: str


# Canonical features_v1 definition matching Prompt 8 and Prompt 9
FEATURES_V1_SPECS: List[FeatureSpec] = [
    FeatureSpec(
        name="accel_x",
        physical_unit="g (9.80665 m/s^2)",
        source_channel="raw_accelerometer_x",
        transformation="none (raw axis)",
        min_physical_bound=-16.0,
        max_physical_bound=16.0,
        description="Linear acceleration along smartphone lateral X-axis in standard g-force units.",
    ),
    FeatureSpec(
        name="accel_y",
        physical_unit="g (9.80665 m/s^2)",
        source_channel="raw_accelerometer_y",
        transformation="none (raw axis)",
        min_physical_bound=-16.0,
        max_physical_bound=16.0,
        description="Linear acceleration along smartphone longitudinal Y-axis in standard g-force units.",
    ),
    FeatureSpec(
        name="accel_z",
        physical_unit="g (9.80665 m/s^2)",
        source_channel="raw_accelerometer_z",
        transformation="none (raw axis)",
        min_physical_bound=-16.0,
        max_physical_bound=16.0,
        description="Linear acceleration along smartphone vertical Z-axis in standard g-force units.",
    ),
    FeatureSpec(
        name="gyro_x",
        physical_unit="rad/s",
        source_channel="raw_gyroscope_x",
        transformation="none (raw axis)",
        min_physical_bound=-35.0,
        max_physical_bound=35.0,
        description="Rotational velocity around smartphone X-axis (pitch rate).",
    ),
    FeatureSpec(
        name="gyro_y",
        physical_unit="rad/s",
        source_channel="raw_gyroscope_y",
        transformation="none (raw axis)",
        min_physical_bound=-35.0,
        max_physical_bound=35.0,
        description="Rotational velocity around smartphone Y-axis (roll rate).",
    ),
    FeatureSpec(
        name="gyro_z",
        physical_unit="rad/s",
        source_channel="raw_gyroscope_z",
        transformation="none (raw axis)",
        min_physical_bound=-35.0,
        max_physical_bound=35.0,
        description="Rotational velocity around smartphone Z-axis (yaw rate).",
    ),
    FeatureSpec(
        name="accel_mag",
        physical_unit="g (9.80665 m/s^2)",
        source_channel="accel_x, accel_y, accel_z",
        transformation="sqrt(ax^2 + ay^2 + az^2)",
        min_physical_bound=0.0,
        max_physical_bound=28.0,
        description="Total 3D acceleration vector Euclidean norm (gravity + dynamic acceleration).",
    ),
    FeatureSpec(
        name="gyro_mag",
        physical_unit="rad/s",
        source_channel="gyro_x, gyro_y, gyro_z",
        transformation="sqrt(gx^2 + gy^2 + gz^2)",
        min_physical_bound=0.0,
        max_physical_bound=60.0,
        description="Total 3D angular velocity vector Euclidean norm.",
    ),
]


class FeatureRegistry:
    """
    Authoritative registry and metadata manager for versioned features.
    """

    def __init__(self):
        self._versions: Dict[str, List[FeatureSpec]] = {
            "features_v1": FEATURES_V1_SPECS,
        }

    def get_feature_names(self, version: str = "features_v1") -> List[str]:
        if version not in self._versions:
            raise ValueError(f"Unknown feature version '{version}'. Available: {list(self._versions.keys())}")
        return [f.name for f in self._versions[version]]

    def get_feature_specs(self, version: str = "features_v1") -> List[FeatureSpec]:
        if version not in self._versions:
            raise ValueError(f"Unknown feature version '{version}'. Available: {list(self._versions.keys())}")
        return self._versions[version]

    def compute_feature_distributions(
        self,
        features_array: np.ndarray,
        feature_version: str = "features_v1",
    ) -> Dict[str, FeatureChannelDistribution]:
        """
        Computes summary statistics (mean, std, percentiles) for baseline drift monitoring.
        features_array: Shape (N, sequence_length, channels) or (N_samples, channels)
        """
        feature_names = self.get_feature_names(feature_version)
        if features_array.ndim == 3:
            # Flatten (N, T, C) -> (N*T, C)
            flat = features_array.reshape(-1, features_array.shape[-1])
        else:
            flat = features_array

        distributions: Dict[str, FeatureChannelDistribution] = {}
        for idx, feat_name in enumerate(feature_names):
            col = flat[:, idx]
            valid_col = col[~np.isnan(col) & ~np.isinf(col)]
            if len(valid_col) == 0:
                continue

            distributions[feat_name] = FeatureChannelDistribution(
                channel=feat_name,
                count=int(len(valid_col)),
                mean=float(np.mean(valid_col)),
                std=float(np.std(valid_col)),
                min=float(np.min(valid_col)),
                p01=float(np.percentile(valid_col, 1)),
                p05=float(np.percentile(valid_col, 5)),
                p25=float(np.percentile(valid_col, 25)),
                median=float(np.median(valid_col)),
                p75=float(np.percentile(valid_col, 75)),
                p95=float(np.percentile(valid_col, 95)),
                p99=float(np.percentile(valid_col, 99)),
                max=float(np.max(valid_col)),
                missing_count=int(len(col) - len(valid_col)),
            )

        return distributions


feature_registry = FeatureRegistry()
