"""
TourSafe Feature & Model Drift Detection Engine.
Calculates Population Stability Index (PSI) and Kolmogorov-Smirnov (KS) tests
between live telemetry window streams and baseline training distributions.
Provides configurable thresholds, drift classifications (NORMAL, DRIFTING, CRITICAL),
concept drift status reporting, and non-automated retraining advisories.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy import stats

from ...schemas.ml_lifecycle import (
    DriftStatus,
    FeatureChannelDistribution,
    FeatureDriftMetric,
    ModelDriftReport,
)
from .feature_registry import feature_registry

logger = logging.getLogger("toursafe.ml.drift_detector")


class FeatureDriftDetector:
    """
    Monitors live IMU streaming distributions against baseline training distributions.
    """

    def __init__(
        self,
        psi_drifting_threshold: float = 0.10,
        psi_critical_threshold: float = 0.25,
        num_psi_bins: int = 10,
    ):
        self.psi_drifting = psi_drifting_threshold
        self.psi_critical = psi_critical_threshold
        self.num_bins = num_psi_bins

    def calculate_psi(
        self,
        baseline_samples: np.ndarray,
        current_samples: np.ndarray,
    ) -> float:
        """
        Calculates Population Stability Index (PSI) between baseline and current sample distributions.
        PSI = sum((Actual% - Expected%) * ln(Actual% / Expected%))
        """
        if len(baseline_samples) < 10 or len(current_samples) < 10:
            return 0.0

        # Create quantile bins from baseline
        quantiles = np.linspace(0, 100, self.num_bins + 1)
        bin_edges = np.percentile(baseline_samples, quantiles)
        bin_edges[0] = -np.inf
        bin_edges[-1] = np.inf

        # Make bin edges strictly monotonic
        for i in range(1, len(bin_edges)):
            if bin_edges[i] <= bin_edges[i - 1]:
                bin_edges[i] = bin_edges[i - 1] + 1e-5

        expected_counts, _ = np.histogram(baseline_samples, bins=bin_edges)
        actual_counts, _ = np.histogram(current_samples, bins=bin_edges)

        # Convert to percentages with epsilon smoothing
        eps = 1e-4
        expected_pct = (expected_counts / len(baseline_samples)) + eps
        actual_pct = (actual_counts / len(current_samples)) + eps

        # Normalize to sum to 1.0
        expected_pct /= np.sum(expected_pct)
        actual_pct /= np.sum(actual_pct)

        psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
        return float(max(0.0, psi))

    def evaluate_feature_drift(
        self,
        feature_name: str,
        baseline_dist: Optional[FeatureChannelDistribution],
        current_values: np.ndarray,
    ) -> FeatureDriftMetric:
        """
        Computes PSI and KS-test for a single feature channel.
        """
        valid_vals = current_values[~np.isnan(current_values) & ~np.isinf(current_values)]
        if len(valid_vals) < 10 or baseline_dist is None:
            return FeatureDriftMetric(
                feature_name=feature_name,
                psi_score=0.0,
                ks_statistic=0.0,
                ks_p_value=1.0,
                status=DriftStatus.UNKNOWN,
                training_mean=baseline_dist.mean if baseline_dist else 0.0,
                current_mean=float(np.mean(valid_vals)) if len(valid_vals) > 0 else 0.0,
                training_std=baseline_dist.std if baseline_dist else 1.0,
                current_std=float(np.std(valid_vals)) if len(valid_vals) > 0 else 1.0,
                details="Insufficient sample points for statistical evaluation",
            )

        # Synthesize representative baseline sample from stored percentiles & moments
        # using normal approximation with empirical percentiles
        b_mean = baseline_dist.mean
        b_std = max(1e-5, baseline_dist.std)
        sim_baseline = np.random.normal(b_mean, b_std, size=min(1000, len(valid_vals)))

        psi = self.calculate_psi(sim_baseline, valid_vals)
        ks_res = stats.ks_2samp(sim_baseline, valid_vals)
        ks_stat = float(ks_res.statistic)
        ks_pval = float(ks_res.pvalue)

        curr_mean = float(np.mean(valid_vals))
        curr_std = float(np.std(valid_vals))

        if psi >= self.psi_critical:
            status = DriftStatus.CRITICAL
            details = f"Severe distribution shift (PSI={psi:.4f} >= {self.psi_critical})"
        elif psi >= self.psi_drifting:
            status = DriftStatus.DRIFTING
            details = f"Moderate distribution drift (PSI={psi:.4f} >= {self.psi_drifting})"
        else:
            status = DriftStatus.NORMAL
            details = f"Feature distribution stable (PSI={psi:.4f} < {self.psi_drifting})"

        return FeatureDriftMetric(
            feature_name=feature_name,
            psi_score=round(psi, 4),
            ks_statistic=round(ks_stat, 4),
            ks_p_value=round(ks_pval, 4),
            status=status,
            training_mean=round(b_mean, 4),
            current_mean=round(curr_mean, 4),
            training_std=round(b_std, 4),
            current_std=round(curr_std, 4),
            details=details,
        )

    def evaluate_live_window_drift(
        self,
        model_version: str,
        feature_version: str,
        baseline_distributions: Dict[str, FeatureChannelDistribution],
        window_feature_tensors: List[np.ndarray],  # list of (150, 8) arrays
    ) -> ModelDriftReport:
        """
        Aggregates multi-window live streaming observations into a comprehensive ModelDriftReport.
        """
        if not window_feature_tensors:
            return ModelDriftReport(
                model_version=model_version,
                feature_version=feature_version,
                window_count_evaluated=0,
                overall_drift_status=DriftStatus.NORMAL,
                max_psi_score=0.0,
                feature_drifts=[],
                concept_drift_status="CONCEPT DRIFT NOT MEASURABLE (NO VERIFIED REAL-TIME GROUND TRUTH)",
                retraining_recommended=False,
            )

        # Concatenate into (Total_Timesteps, Channels)
        flat_data = np.concatenate(window_feature_tensors, axis=0)
        channel_names = feature_registry.get_feature_names(feature_version)

        feature_metrics: List[FeatureDriftMetric] = []
        max_psi = 0.0

        for idx, feat_name in enumerate(channel_names):
            if idx < flat_data.shape[1]:
                col_vals = flat_data[:, idx]
                b_dist = baseline_distributions.get(feat_name)
                m = self.evaluate_feature_drift(feat_name, b_dist, col_vals)
                feature_metrics.append(m)
                if m.psi_score > max_psi:
                    max_psi = m.psi_score

        if max_psi >= self.psi_critical:
            overall = DriftStatus.CRITICAL
            rec = True
            reason = f"Critical feature drift detected on {sum(1 for f in feature_metrics if f.status == DriftStatus.CRITICAL)} channels (max PSI={max_psi:.4f})"
        elif max_psi >= self.psi_drifting:
            overall = DriftStatus.DRIFTING
            rec = True
            reason = f"Moderate feature drift observed across IMU channels (max PSI={max_psi:.4f})"
        else:
            overall = DriftStatus.NORMAL
            rec = False
            reason = None

        return ModelDriftReport(
            model_version=model_version,
            feature_version=feature_version,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            window_count_evaluated=len(window_feature_tensors),
            overall_drift_status=overall,
            max_psi_score=round(max_psi, 4),
            feature_drifts=feature_metrics,
            concept_drift_status="CONCEPT DRIFT NOT MEASURABLE (NO VERIFIED REAL-TIME GROUND TRUTH)",
            retraining_recommended=rec,
            retraining_reason=reason,
        )


drift_detector = FeatureDriftDetector()
