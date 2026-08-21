"""
TourSafe Anomaly Threshold Calibration.
Calibrates statistical and operational anomaly thresholds from normal validation
reconstruction error distributions.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


@dataclass
class ThresholdCalibrationResult:
    method: str
    primary_threshold: float
    warning_threshold: float
    critical_threshold: float
    val_score_mean: float
    val_score_std: float
    val_score_median: float
    val_score_iqr: float
    val_score_p95: float
    val_score_p99: float
    calibrated_at_epoch: Optional[int] = None
    tuning_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "primary_threshold": round(float(self.primary_threshold), 6),
            "warning_threshold": round(float(self.warning_threshold), 6),
            "critical_threshold": round(float(self.critical_threshold), 6),
            "val_score_mean": round(float(self.val_score_mean), 6),
            "val_score_std": round(float(self.val_score_std), 6),
            "val_score_median": round(float(self.val_score_median), 6),
            "val_score_iqr": round(float(self.val_score_iqr), 6),
            "val_score_p95": round(float(self.val_score_p95), 6),
            "val_score_p99": round(float(self.val_score_p99), 6),
            "calibrated_at_epoch": self.calibrated_at_epoch,
            "tuning_metadata": self.tuning_metadata,
        }

    def save(self, json_path: Union[str, Path]) -> None:
        p = Path(json_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, json_path: Union[str, Path]) -> "ThresholdCalibrationResult":
        p = Path(json_path)
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        return cls(
            method=d["method"],
            primary_threshold=d["primary_threshold"],
            warning_threshold=d["warning_threshold"],
            critical_threshold=d["critical_threshold"],
            val_score_mean=d["val_score_mean"],
            val_score_std=d["val_score_std"],
            val_score_median=d["val_score_median"],
            val_score_iqr=d["val_score_iqr"],
            val_score_p95=d["val_score_p95"],
            val_score_p99=d["val_score_p99"],
            calibrated_at_epoch=d.get("calibrated_at_epoch"),
            tuning_metadata=d.get("tuning_metadata", {}),
        )


class AnomalyThresholdCalibrator:
    """
    Calibrates statistical thresholds on normal validation reconstruction error distributions.
    Supports Percentile, Gaussian (mean + k*std), and IQR (Q3 + 1.5*IQR) methodologies.
    """

    def __init__(self, default_method: str = "percentile_99"):
        self.default_method = default_method

    def calibrate(
        self,
        val_reconstruction_errors: np.ndarray,
        method: Optional[str] = None,
        k_sigma: float = 3.0,
        epoch: Optional[int] = None,
    ) -> ThresholdCalibrationResult:
        """
        Calculates anomaly threshold parameters on validation normal error scores.

        Parameters
        ----------
        val_reconstruction_errors : np.ndarray of shape (N_val,)
        method : str ('percentile_99', 'gaussian_3sigma', 'iqr')
        k_sigma : float
        epoch : Optional[int]
        """
        scores = np.asarray(val_reconstruction_errors, dtype=np.float64)
        if len(scores) < 5:
            raise ValueError(f"Need at least 5 validation error scores to calibrate threshold, got {len(scores)}")

        cal_method = method or self.default_method

        mean = float(np.mean(scores))
        std = float(np.std(scores))
        median = float(np.median(scores))

        q25 = float(np.percentile(scores, 25.0))
        q75 = float(np.percentile(scores, 75.0))
        iqr = q75 - q25

        p95 = float(np.percentile(scores, 95.0))
        p98 = float(np.percentile(scores, 98.0))
        p99 = float(np.percentile(scores, 99.0))
        p99_5 = float(np.percentile(scores, 99.5))

        if cal_method == "gaussian_3sigma":
            primary_th = mean + k_sigma * std
            warning_th = mean + 2.0 * std
            critical_th = mean + 4.0 * std
        elif cal_method == "iqr":
            primary_th = q75 + 1.5 * iqr
            warning_th = q75 + 1.0 * iqr
            critical_th = q75 + 3.0 * iqr
        else:  # 'percentile_99'
            primary_th = p99
            warning_th = p95
            critical_th = p99_5

        # Ensure warning < primary <= critical
        warning_th = min(warning_th, primary_th * 0.85)
        critical_th = max(critical_th, primary_th * 1.3)

        return ThresholdCalibrationResult(
            method=cal_method,
            primary_threshold=primary_th,
            warning_threshold=warning_th,
            critical_threshold=critical_th,
            val_score_mean=mean,
            val_score_std=std,
            val_score_median=median,
            val_score_iqr=iqr,
            val_score_p95=p95,
            val_score_p99=p99,
            calibrated_at_epoch=epoch,
            tuning_metadata={
                "k_sigma": k_sigma,
                "n_val_samples": len(scores),
                "q25": round(q25, 6),
                "q75": round(q75, 6),
                "p98": round(p98, 6),
            },
        )
