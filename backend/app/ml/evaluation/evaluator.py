"""
TourSafe Model Evaluation Engine.
Computes reconstruction errors, ROC-AUC, PR-AUC, F1-Scores, Confusion Matrices,
and comparative baseline benchmarks.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
)
import torch

from ..models.lstm_autoencoder import TourSafeLSTMAutoencoder
from ..models.baselines import KinematicPeakDetector, IsolationForestDetector
from .threshold import ThresholdCalibrationResult


@dataclass
class AnomalyEvaluationReport:
    model_name: str
    roc_auc: float
    pr_auc: float
    best_f1: float
    precision_at_calibrated_threshold: float
    recall_at_calibrated_threshold: float
    f1_at_calibrated_threshold: float
    specificity: float
    false_positive_rate: float
    false_negative_rate: float
    confusion_matrix: Dict[str, int]
    calibrated_threshold: float
    activity_error_breakdown: Dict[str, Dict[str, float]]
    baseline_comparisons: Dict[str, Dict[str, float]] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "roc_auc": round(self.roc_auc, 4),
            "pr_auc": round(self.pr_auc, 4),
            "best_f1": round(self.best_f1, 4),
            "precision": round(self.precision_at_calibrated_threshold, 4),
            "recall": round(self.recall_at_calibrated_threshold, 4),
            "f1_score": round(self.f1_at_calibrated_threshold, 4),
            "specificity": round(self.specificity, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "false_negative_rate": round(self.false_negative_rate, 4),
            "confusion_matrix": self.confusion_matrix,
            "calibrated_threshold": round(self.calibrated_threshold, 6),
            "activity_error_breakdown": self.activity_error_breakdown,
            "baseline_comparisons": self.baseline_comparisons,
            "summary": self.summary,
        }


class ModelEvaluator:
    """
    Evaluates LSTM Autoencoder anomaly detection performance on held-out test datasets.
    """

    def __init__(self, device: str = "cpu"):
        self.device = torch.device(device)

    def compute_model_scores(
        self,
        model: TourSafeLSTMAutoencoder,
        X_test: np.ndarray,
        batch_size: int = 64,
    ) -> np.ndarray:
        """
        Computes MSE reconstruction error per test window.
        """
        model.eval()
        model.to(self.device)

        scores = []
        n_samples = len(X_test)

        with torch.no_grad():
            for i in range(0, n_samples, batch_size):
                batch_np = X_test[i : i + batch_size]
                batch_tensor = torch.from_numpy(batch_np.astype(np.float32)).to(self.device)
                batch_scores = model.compute_reconstruction_error(batch_tensor, error_type="mse")
                scores.extend(batch_scores.cpu().numpy().tolist())

        return np.array(scores, dtype=np.float64)

    def evaluate(
        self,
        model: TourSafeLSTMAutoencoder,
        X_test: np.ndarray,
        y_test: np.ndarray,
        test_activities: List[str],
        threshold_result: ThresholdCalibrationResult,
        X_train: Optional[np.ndarray] = None,
        X_val: Optional[np.ndarray] = None,
    ) -> AnomalyEvaluationReport:
        """
        Runs comprehensive benchmark evaluation of the LSTM Autoencoder against ground truth and baselines.
        """
        scores = self.compute_model_scores(model, X_test)
        threshold = threshold_result.primary_threshold

        y_true = np.asarray(y_test, dtype=int)
        y_pred = (scores >= threshold).astype(int)

        # Compute metric curves
        try:
            roc_auc = float(roc_auc_score(y_true, scores))
        except Exception:
            roc_auc = 0.5

        try:
            pr_auc = float(average_precision_score(y_true, scores))
        except Exception:
            pr_auc = 0.0

        # Classification metrics at calibrated threshold
        precision = float(precision_score(y_true, y_pred, zero_division=0))
        recall = float(recall_score(y_true, y_pred, zero_division=0))
        f1 = float(f1_score(y_true, y_pred, zero_division=0))

        # Confusion Matrix
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        tn, fp, fn, tp = int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1])

        specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
        fpr = float(fp / (tn + fp)) if (tn + fp) > 0 else 0.0
        fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

        # Find best possible F1 across precision-recall curve
        precisions, recalls, thresholds = precision_recall_curve(y_true, scores)
        f1_scores = 2 * (precisions * recalls) / np.maximum(precisions + recalls, 1e-8)
        best_f1 = float(np.max(f1_scores)) if len(f1_scores) > 0 else f1

        # Activity Breakdown
        activity_stats: Dict[str, Dict[str, float]] = {}
        unique_acts = sorted(list(set(test_activities)))
        for act in unique_acts:
            act_mask = np.array([a == act for a in test_activities])
            act_scores = scores[act_mask]
            act_preds = y_pred[act_mask]
            activity_stats[act] = {
                "count": int(np.sum(act_mask)),
                "mean_reconstruction_error": round(float(np.mean(act_scores)), 6),
                "median_reconstruction_error": round(float(np.median(act_scores)), 6),
                "std_reconstruction_error": round(float(np.std(act_scores)), 6),
                "max_reconstruction_error": round(float(np.max(act_scores)), 6),
                "anomaly_detection_rate": round(float(np.mean(act_preds)), 4),
            }

        # Baseline Comparisons
        baselines_dict: Dict[str, Dict[str, float]] = {}

        if X_train is not None:
            # 1. Kinematic Peak Baseline
            peak_detector = KinematicPeakDetector()
            peak_detector.fit(X_train)
            peak_scores = peak_detector.predict_scores(X_test)
            try:
                peak_roc = float(roc_auc_score(y_true, peak_scores))
                peak_pr = float(average_precision_score(y_true, peak_scores))
            except Exception:
                peak_roc, peak_pr = 0.5, 0.0

            peak_preds = peak_detector.predict(X_test)
            baselines_dict["kinematic_peak_detector"] = {
                "roc_auc": round(peak_roc, 4),
                "pr_auc": round(peak_pr, 4),
                "f1_score": round(float(f1_score(y_true, peak_preds, zero_division=0)), 4),
                "precision": round(float(precision_score(y_true, peak_preds, zero_division=0)), 4),
                "recall": round(float(recall_score(y_true, peak_preds, zero_division=0)), 4),
            }

            # 2. Isolation Forest Baseline
            try:
                iso_forest = IsolationForestDetector()
                iso_forest.fit(X_train)
                iso_scores = iso_forest.predict_scores(X_test)
                iso_roc = float(roc_auc_score(y_true, iso_scores))
                iso_pr = float(average_precision_score(y_true, iso_scores))
                iso_preds = iso_forest.predict(X_test)
                baselines_dict["isolation_forest"] = {
                    "roc_auc": round(iso_roc, 4),
                    "pr_auc": round(iso_pr, 4),
                    "f1_score": round(float(f1_score(y_true, iso_preds, zero_division=0)), 4),
                    "precision": round(float(precision_score(y_true, iso_preds, zero_division=0)), 4),
                    "recall": round(float(recall_score(y_true, iso_preds, zero_division=0)), 4),
                }
            except Exception as e:
                baselines_dict["isolation_forest"] = {"error": str(e)}

        return AnomalyEvaluationReport(
            model_name="TourSafeLSTMAutoencoder",
            roc_auc=roc_auc,
            pr_auc=pr_auc,
            best_f1=best_f1,
            precision_at_calibrated_threshold=precision,
            recall_at_calibrated_threshold=recall,
            f1_at_calibrated_threshold=f1,
            specificity=specificity,
            false_positive_rate=fpr,
            false_negative_rate=fnr,
            confusion_matrix={"tn": tn, "fp": fp, "fn": fn, "tp": tp},
            calibrated_threshold=threshold,
            activity_error_breakdown=activity_stats,
            baseline_comparisons=baselines_dict,
            summary={
                "total_test_windows": len(y_true),
                "normal_windows": int(np.sum(y_true == 0)),
                "anomalous_windows": int(np.sum(y_true == 1)),
                "evaluation_verdict": "PASSED" if roc_auc >= 0.85 and recall >= 0.80 else "NEEDS_TUNING",
            },
        )
